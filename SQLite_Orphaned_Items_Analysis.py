import sqlite3
import os
from prettytable import PrettyTable
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict, Counter

class OrphanedItemsAnalyzer:
    """Analyze orphaned items to identify deleted characters"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        
        # Enhanced inventory type mappings for Conan Exiles
        self.inv_type_mapping = {
            0: "Player Inventory",
            1: "Player Hotbar", 
            2: "Equipment Slots",
            3: "Loot Bag",
            4: "Large Chest",
            5: "Small Chest",
            6: "Reinforced Chest",
            7: "Armorer's Bench",
            8: "Blacksmith's Bench",
            9: "Carpenter's Bench",
            10: "Tannery",
            11: "Alchemist's Bench",
            12: "Firebowl Cauldron",
            13: "Furnace",
            14: "Improved Furnace",
            15: "Preservation Box",
            16: "Fluid Press",
            17: "Compost Heap",
            18: "Dryer",
            19: "Wheel of Pain",
            20: "Torturer's Worktable",
            21: "Map Room",
            22: "Vault",
            23: "Animal Pen",
            24: "Stable",
            25: "Improved Animal Pen",
            26: "Large Animal Pen"
        }
        
        # Personal vs External storage classification
        self.personal_inventory_types = {0, 1, 2, 3}  # Inventory, Hotbar, Equipment, Loot Bags
        self.external_storage_types = {4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26}
        
    @staticmethod
    def format_number(num: int) -> str:
        """Format number with commas"""
        return f"{num:,}"
    
    def analyze_orphaned_items(self) -> Dict:
        """Comprehensive analysis of orphaned items and their missing owners"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # First, check if necessary tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='item_inventory';")
            if not cursor.fetchone():
                return {"error": "item_inventory table not found"}
                
            # Find character table name
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('characters', 'character', 'players');")
            char_table = cursor.fetchone()
            if not char_table:
                return {"error": "No character table found"}
            char_table_name = char_table[0]
            
            # Get all existing character IDs
            cursor.execute(f"SELECT id FROM {char_table_name}")
            existing_chars = set(row[0] for row in cursor.fetchall())
            
            # Get all existing structure/chest IDs from actor_position
            cursor.execute("SELECT id FROM actor_position")
            existing_structures = set(row[0] for row in cursor.fetchall())
            
            # Find all unique owner_ids from item_inventory
            cursor.execute("SELECT DISTINCT owner_id FROM item_inventory WHERE owner_id IS NOT NULL")
            all_owner_ids = set(row[0] for row in cursor.fetchall())
            
            # CORRECTED LOGIC: Only IDs that are neither characters NOR structures are truly orphaned
            deleted_char_ids = all_owner_ids - existing_chars - existing_structures
            structure_owned_items = all_owner_ids & existing_structures
            
            # NEW: Analyze active players potentially affected by aggressive cleanup
            affected_active_players = self.analyze_cleanup_damage(cursor, char_table_name)
            
            # Analyze orphaned items by truly deleted characters (not structures)
            deleted_chars_info = []
            for char_id in deleted_char_ids:
                cursor.execute("""
                    SELECT 
                        owner_id,
                        COUNT(*) as item_count,
                        COUNT(DISTINCT inv_type) as inventory_types,
                        COUNT(DISTINCT template_id) as unique_items,
                        GROUP_CONCAT(DISTINCT inv_type) as inv_types_list
                    FROM item_inventory
                    WHERE owner_id = ?
                    GROUP BY owner_id
                """, (char_id,))
                
                result = cursor.fetchone()
                if result:
                    deleted_chars_info.append({
                        'id': result[0],
                        'item_count': result[1],
                        'inventory_types': result[2],
                        'unique_items': result[3],
                        'inv_types_list': result[4]
                    })
            
            # Sort by item count
            deleted_chars_info.sort(key=lambda x: x['item_count'], reverse=True)
            
            # Get inventory type distribution for TRULY orphaned items (not in structures)
            cursor.execute("""
                SELECT 
                    inv_type,
                    COUNT(*) as count,
                    COUNT(DISTINCT owner_id) as unique_owners
                FROM item_inventory
                WHERE owner_id NOT IN (SELECT id FROM {})
                AND owner_id NOT IN (SELECT id FROM actor_position)
                GROUP BY inv_type
                ORDER BY count DESC
            """.format(char_table_name))
            inv_type_distribution = cursor.fetchall()
            
            # Get most common truly orphaned items
            cursor.execute("""
                SELECT 
                    template_id,
                    COUNT(*) as count,
                    COUNT(DISTINCT owner_id) as unique_owners
                FROM item_inventory
                WHERE owner_id NOT IN (SELECT id FROM {})
                AND owner_id NOT IN (SELECT id FROM actor_position)
                GROUP BY template_id
                ORDER BY count DESC
                LIMIT 20
            """.format(char_table_name))
            common_orphaned_items = cursor.fetchall()
            
            # Analyze patterns in deleted character IDs
            id_ranges = self.analyze_id_patterns(deleted_char_ids)
            
            # Check for any character data in other tables
            additional_info = self.check_other_tables(cursor, deleted_char_ids, char_table_name)
            
            conn.close()
            
            return {
                'total_deleted_characters': len(deleted_char_ids),
                'total_orphaned_items': sum(char['item_count'] for char in deleted_chars_info),
                'deleted_characters': deleted_chars_info,
                'inventory_type_distribution': inv_type_distribution,
                'common_orphaned_items': common_orphaned_items,
                'id_ranges': id_ranges,
                'additional_info': additional_info,
                'existing_characters': len(existing_chars),
                'existing_structures': len(existing_structures),
                'structure_owned_items': len(structure_owned_items),
                'char_table_name': char_table_name,
                'affected_active_players': affected_active_players,
                'cleanup_damage_detected': len(affected_active_players) > 0,
                # NEW: Important distinction
                'items_in_structures_count': sum(1 for _ in structure_owned_items),
                'truly_orphaned_vs_in_structures': {
                    'orphaned': len(deleted_char_ids),
                    'in_structures': len(structure_owned_items)
                }
            }
            
        except Exception as e:
            return {"error": f"Analysis error: {e}"}
    
    def analyze_cleanup_damage(self, cursor, char_table_name: str) -> List[Dict]:
        """NEW: Analyze if recent cleanup affected active players' external storage"""
        try:
            # Get active characters (alive and recently online)
            cursor.execute(f"""
                SELECT id, char_name, playerId, lastTimeOnline
                FROM {char_table_name} 
                WHERE isAlive = 1
            """)
            active_chars = cursor.fetchall()
            
            affected_players = []
            
            for char_id, char_name, player_id, last_online in active_chars:
                # Check what inventory types this character has
                cursor.execute("""
                    SELECT inv_type, COUNT(*) as item_count
                    FROM item_inventory 
                    WHERE owner_id = ?
                    GROUP BY inv_type
                    ORDER BY inv_type
                """, (char_id,))
                
                remaining_inventory = cursor.fetchall()
                remaining_types = set(row[0] for row in remaining_inventory)
                
                # Check if they have personal items but missing external storage
                has_personal_items = bool(self.personal_inventory_types & remaining_types)
                has_external_storage = bool(self.external_storage_types & remaining_types)
                
                total_items = sum(row[1] for row in remaining_inventory)
                
                # Red flag: Has personal items but no external storage (suspicious for active players)
                if has_personal_items and not has_external_storage and total_items > 0:
                    affected_players.append({
                        'char_id': char_id,
                        'char_name': char_name,
                        'player_id': player_id,
                        'last_online': last_online,
                        'total_items': total_items,
                        'has_personal_only': True,
                        'missing_external': True,
                        'inventory_types': remaining_types
                    })
                elif total_items == 0:
                    # Completely empty inventory for active character
                    affected_players.append({
                        'char_id': char_id,
                        'char_name': char_name,
                        'player_id': player_id,
                        'last_online': last_online,
                        'total_items': 0,
                        'has_personal_only': False,
                        'missing_external': True,
                        'inventory_types': set()
                    })
            
            return affected_players
            
        except Exception as e:
            print(f"Warning: Could not analyze cleanup damage: {e}")
            return []
    
    def analyze_id_patterns(self, deleted_ids: set) -> Dict:
        """Analyze patterns in deleted character IDs"""
        if not deleted_ids:
            return {}
            
        sorted_ids = sorted(deleted_ids)
        
        # Find contiguous ranges
        ranges = []
        start = sorted_ids[0]
        end = start
        
        for i in range(1, len(sorted_ids)):
            if sorted_ids[i] == end + 1:
                end = sorted_ids[i]
            else:
                if start == end:
                    ranges.append(f"{start}")
                else:
                    ranges.append(f"{start}-{end}")
                start = sorted_ids[i]
                end = start
        
        # Add last range
        if start == end:
            ranges.append(f"{start}")
        else:
            ranges.append(f"{start}-{end}")
        
        # Analyze ID distribution
        min_id = min(deleted_ids)
        max_id = max(deleted_ids)
        
        return {
            'min_deleted_id': min_id,
            'max_deleted_id': max_id,
            'id_ranges': ranges[:10],  # First 10 ranges
            'total_ranges': len(ranges),
            'appears_sequential': len(ranges) < len(deleted_ids) / 10  # Many sequential deletions
        }
    
    def check_other_tables(self, cursor, deleted_ids: set, char_table_name: str) -> Dict:
        """Check other tables for traces of deleted characters"""
        traces = {}
        
        # Sample of deleted IDs to check
        sample_ids = list(deleted_ids)[:5]
        
        # Check common related tables
        related_tables = [
            ('game_events', 'player_id'),
            ('game_events', 'target_id'),
            ('buildings', 'owner_id'),
            ('buildable_health', 'owner_id'),
            ('actor_position', 'id'),
            ('properties', 'object_id')
        ]
        
        for table, column in related_tables:
            try:
                # Check if table exists
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}';")
                if not cursor.fetchone():
                    continue
                    
                # Check if column exists
                cursor.execute(f"PRAGMA table_info({table});")
                columns = [col[1] for col in cursor.fetchall()]
                if column not in columns:
                    continue
                
                # Check for references to deleted characters
                placeholders = ','.join(['?' for _ in sample_ids])
                cursor.execute(f"""
                    SELECT COUNT(*) 
                    FROM {table} 
                    WHERE {column} IN ({placeholders})
                """, sample_ids)
                
                count = cursor.fetchone()[0]
                if count > 0:
                    traces[f"{table}.{column}"] = count
                    
            except Exception as e:
                continue
                
        return traces
    
    def generate_recovery_possibilities(self, analysis: Dict) -> List[Dict]:
        """Generate possibilities for recovering character information"""
        possibilities = []
        
        # NEW: Check for cleanup damage
        if analysis.get('cleanup_damage_detected'):
            possibilities.append({
                'priority': 'HIGH',
                'method': '🚨 CLEANUP DAMAGE DETECTED',
                'description': 'Active players appear to have lost external storage items (chests, crafting benches)',
                'action': 'Consider restoring from backup or compensating affected players'
            })
        
        if analysis.get('additional_info'):
            possibilities.append({
                'priority': 'MEDIUM',
                'method': 'Check game_events table',
                'description': 'Game events might contain character names or actions',
                'query': "SELECT DISTINCT player_id, COUNT(*) FROM game_events WHERE player_id IN (deleted_ids) GROUP BY player_id"
            })
            
        if analysis.get('id_ranges', {}).get('appears_sequential'):
            possibilities.append({
                'priority': 'LOW',
                'method': 'Mass deletion detected',
                'description': 'Sequential ID ranges suggest mass deletion event (wipe, cleanup, or migration)',
                'action': 'Check server logs around deletion time'
            })
            
        possibilities.append({
            'priority': 'HIGH',
            'method': 'Check backup databases',
            'description': 'Older backup files might contain character information',
            'action': 'Compare with backup game.db files if available'
        })
        
        return possibilities
    
    def generate_safe_cleanup_commands(self, analysis: Dict) -> List[Dict]:
        """NEW: Generate safer cleanup commands that preserve external storage"""
        commands = []
        
        if analysis.get('cleanup_damage_detected'):
            commands.append({
                'title': '⚠️ DAMAGE CONTROL - DO NOT RUN CLEANUP YET',
                'description': 'Active players have been affected by previous cleanup',
                'sql': '-- DO NOT RUN ANY CLEANUP UNTIL DAMAGE IS ASSESSED AND ADDRESSED\n-- Previous cleanup has already damaged player inventories',
                'impact': 'RECOVERY NEEDED - Restore from backup or compensate players',
                'warning': 'Restore from backup or compensate players first'
            })
            # When damage is detected, don't show other cleanup options
            return commands
        
        # Check if there are actually any truly orphaned items
        if analysis.get('total_orphaned_items', 0) == 0:
            commands.append({
                'title': '🎉 NO CLEANUP NEEDED - DATABASE IS HEALTHY!',
                'description': 'No truly orphaned items found. All items belong to active characters or structures.',
                'sql': '''-- NO CLEANUP REQUIRED! 🎉
-- Your database is operating perfectly!
-- 
-- All items are properly owned by either:
-- 1. Active characters (personal inventory, hotbar, equipment)
-- 2. Structures (chests, crafting stations, vaults, etc.)
--
-- This is exactly how Conan Exiles is designed to work!
-- Items in chests are NOT orphaned - they are properly stored.''',
                'impact': '✅ PERFECT - No action needed, database is healthy'
            })
            return commands
        
        # Show the impact comparison
        comparison_info = ""
        if analysis.get('structure_owned_items', 0) > 0:
            structure_items = analysis.get('structure_owned_items', 0)
            orphaned_items = analysis.get('total_orphaned_items', 0)
            comparison_info = f"\n-- Items in structures (SAFE): {structure_items:,}\n-- Truly orphaned items: {orphaned_items:,}"
        
        # Safe cleanup options - ONLY delete from truly orphaned character IDs
        commands.append({
            'title': '🔒 RECOMMENDED: Truly Orphaned Items Only',
            'description': 'Only delete items from owner IDs that exist in neither characters nor actor_position tables',
            'sql': f'''-- RECOMMENDED CLEANUP: Only truly orphaned items
-- This is the ONLY safe cleanup approach!
{comparison_info}
--
-- This deletes ONLY items from owner IDs that are:
-- 1. NOT in the characters table (not active characters)
-- 2. NOT in the actor_position table (not chests/structures)
DELETE FROM item_inventory 
WHERE owner_id NOT IN (SELECT id FROM {analysis['char_table_name']})  -- Not a character
AND owner_id NOT IN (SELECT id FROM actor_position);  -- Not a structure/chest

-- This will remove {analysis.get('total_orphaned_items', 0):,} truly orphaned items
-- This will PRESERVE ALL items in chests, crafting stations, and structures''',
            'impact': f'SAFE - Removes only {analysis.get("total_orphaned_items", 0):,} truly orphaned items'
        })
        
        commands.append({
            'title': '🔒 CONSERVATIVE: Personal Items from Deleted Characters Only',
            'description': 'Delete only personal inventory items from truly deleted characters',
            'sql': f'''-- CONSERVATIVE CLEANUP: Personal items from truly deleted characters only
DELETE FROM item_inventory 
WHERE owner_id NOT IN (SELECT id FROM {analysis['char_table_name']})  -- Not a character
AND owner_id NOT IN (SELECT id FROM actor_position)  -- Not a structure
AND inv_type IN (0, 1, 2, 3); -- Personal inventory types only (inventory, hotbar, equipment, loot bags)

-- This preserves ALL items in chests, crafting stations, and other structures
-- Even more conservative than the recommended approach''',
            'impact': 'ULTRA SAFE - Most conservative approach, preserves everything possible'
        })
        
        # Educational warning about the dangerous approaches
        commands.append({
            'title': '🚨 DANGEROUS: "Not Owned by Characters" (DESTROYS CHESTS)',
            'description': 'This is the flawed logic that has destroyed countless server databases',
            'sql': f'''-- ❌ DANGEROUS AND WRONG APPROACH - DO NOT USE!
-- DELETE FROM item_inventory WHERE owner_id NOT IN (SELECT id FROM characters);

-- 🚨 WHY THIS DESTROYS SERVERS:
-- 1. Items in chests have owner_id = chest_id (from actor_position table)  
-- 2. Chest IDs are NOT in the characters table (they're structures!)
-- 3. This command treats ALL CHESTS as "deleted characters"
-- 4. Result: DESTROYS ALL ITEMS IN ALL CHESTS AND CRAFTING STATIONS!
--
-- 📊 IMPACT ON YOUR DATABASE:
-- This would delete items from {analysis.get('structure_owned_items', 0):,} structures
-- This would destroy items in thousands of chests and crafting stations
-- This would affect every single player on your server
-- 
-- ✅ CORRECT UNDERSTANDING:
-- Items can be owned by:
-- - Character IDs (personal inventory, hotbar, equipment)  
-- - Structure IDs (chests, crafting benches, vaults, etc.)
-- 
-- Only delete items owned by IDs that exist in NEITHER table!
-- 
-- 🎯 YOUR SERVER'S REALITY:
-- Truly orphaned items needing cleanup: {analysis.get('total_orphaned_items', 0):,}
-- Items safely stored in structures: {analysis.get('structure_owned_items', 0):,}
-- 
-- Your database is {analysis.get('total_orphaned_items', 0):,} items away from perfect!''',
            'impact': f'🚨 CATASTROPHIC - Would destroy {analysis.get("structure_owned_items", 0):,} items in player chests!',
            'warning': 'DO NOT USE - This approach has destroyed countless Conan Exiles servers!'
        })
        
        return commands
    
    def count_items_by_types(self, analysis: Dict, inv_types: set) -> int:
        """Helper to count items by inventory types"""
        total = 0
        for inv_type, count, _ in analysis.get('inventory_type_distribution', []):
            if inv_type in inv_types:
                total += count
        return total
    
    def print_analysis(self, analysis: Dict):
        """Print the orphaned items analysis with enhanced safety warnings"""
        if "error" in analysis:
            print(f"\n❌ Error: {analysis['error']}")
            return
            
        print("\n" + "="*80)
        print("🔍 CONAN EXILES DATABASE HEALTH ANALYZER")
        print("="*80)
        
        # NEW: Priority warning for cleanup damage
        if analysis.get('cleanup_damage_detected'):
            print("\n" + "🚨" * 20)
            print("⚠️ CRITICAL: CLEANUP DAMAGE DETECTED!")
            print("🚨" * 20)
            print(f"❌ {len(analysis['affected_active_players'])} active players appear to have lost external storage items!")
            print("❌ This suggests a previous cleanup command was too aggressive.")
            print("❌ DO NOT run any more cleanup commands until this is addressed!")
            print("✅ Recommended: Restore from backup or compensate affected players.")
            print("🚨" * 20)
        
        print(f"\n📊 Summary:")
        print(f"Existing Characters: {self.format_number(analysis['existing_characters'])}")
        print(f"Existing Structures: {self.format_number(analysis.get('existing_structures', 0))}")
        print(f"Items in Structures: {self.format_number(analysis.get('structure_owned_items', 0))} ✅ NORMAL")
        print(f"Truly Orphaned Items: {self.format_number(analysis['total_orphaned_items'])}")
        print(f"Character Table: {analysis['char_table_name']}")
        
        # NEW: Health Assessment
        total_items_in_structures = analysis.get('structure_owned_items', 0)
        truly_orphaned = analysis['total_orphaned_items']
        
        if truly_orphaned == 0:
            print(f"\n✅ DATABASE HEALTH: EXCELLENT")
            print(f"🎉 No cleanup needed! All items are properly owned.")
        elif truly_orphaned < 1000:
            print(f"\n✅ DATABASE HEALTH: VERY GOOD")
            print(f"💡 Minimal cleanup needed - only {truly_orphaned} truly orphaned items.")
        elif truly_orphaned < 10000:
            print(f"\n⚠️ DATABASE HEALTH: GOOD")
            print(f"🔧 Light cleanup recommended - {truly_orphaned} orphaned items found.")
        else:
            print(f"\n⚠️ DATABASE HEALTH: NEEDS ATTENTION") 
            print(f"🛠️ Cleanup recommended - {truly_orphaned} orphaned items found.")
        
        # NEW: Educational section
        print(f"\n📚 IMPORTANT UNDERSTANDING:")
        print(f"✅ Items in chests/crafting stations = NORMAL (not orphaned)")
        print(f"✅ Structure-owned items = HEALTHY database operation") 
        print(f"❌ Only items with non-existent owner IDs = truly orphaned")
        
        if total_items_in_structures > truly_orphaned * 10:
            print(f"\n🎯 KEY INSIGHT:")
            print(f"Your database is operating normally! Most items are properly")
            print(f"stored in chests and crafting stations, which is exactly how")
            print(f"Conan Exiles is designed to work.")
        
        # Enhanced deletion percentage  
        total_owner_ids = analysis['existing_characters'] + analysis.get('existing_structures', 0) + analysis['total_deleted_characters']
        if total_owner_ids > 0:
            deletion_rate = (analysis['total_deleted_characters'] / total_owner_ids * 100)
            print(f"Truly Deleted Owner IDs: {deletion_rate:.1f}% of all owner IDs ever created")
        
        print(f"💡 Note: Deleted Character IDs ≠ Unique Players Lost")
        print(f"   Many IDs come from character respawns, resets, and server maintenance")
        
        # NEW: Show affected active players if detected
        if analysis.get('affected_active_players'):
            print(f"\n🚨 AFFECTED ACTIVE PLAYERS:")
            affected_table = PrettyTable()
            affected_table.field_names = ["Character Name", "Player ID", "Items Left", "Status"]
            
            for player in analysis['affected_active_players'][:15]:  # Show first 15
                status = "Missing External Storage" if player['missing_external'] and player['total_items'] > 0 else "All Items Lost"
                affected_table.add_row([
                    player['char_name'] or f"ID:{player['char_id']}",
                    player['player_id'],
                    player['total_items'],
                    status
                ])
            
            print(affected_table)
            
            if len(analysis['affected_active_players']) > 15:
                print(f"\n... and {len(analysis['affected_active_players']) - 15} more affected players")
        
        # ID Pattern Analysis
        if analysis.get('id_ranges'):
            print(f"\n🔢 Deleted Character ID Patterns:")
            id_info = analysis['id_ranges']
            print(f"ID Range: {id_info['min_deleted_id']} to {id_info['max_deleted_id']}")
            print(f"Pattern: {'Sequential deletions detected' if id_info['appears_sequential'] else 'Random deletions'}")
            print(f"ID Ranges (first 10): {', '.join(id_info['id_ranges'])}")
            if id_info['total_ranges'] > 10:
                print(f"... and {id_info['total_ranges'] - 10} more ranges")
        
        # Top deleted characters by item count
        if analysis['deleted_characters']:
            print(f"\n👻 Top Deleted Characters by Item Count:")
            char_table = PrettyTable()
            char_table.field_names = ["Rank", "Character ID", "Items", "Inv Types", "Unique Items", "Inventory Types Used"]
            
            for i, char in enumerate(analysis['deleted_characters'][:20], 1):
                inv_types = char['inv_types_list'].split(',') if char['inv_types_list'] else []
                inv_types_display = ', '.join(inv_types[:3])
                if len(inv_types) > 3:
                    inv_types_display += f" +{len(inv_types)-3} more"
                    
                char_table.add_row([
                    i,
                    char['id'],
                    self.format_number(char['item_count']),
                    char['inventory_types'],
                    char['unique_items'],
                    inv_types_display
                ])
            print(char_table)
            
            if len(analysis['deleted_characters']) > 20:
                print(f"\n... and {len(analysis['deleted_characters']) - 20} more deleted characters")
        
        # Inventory type distribution with enhanced mapping
        if analysis['inventory_type_distribution']:
            print(f"\n📦 Orphaned Items by Inventory Type:")
            inv_table = PrettyTable()
            inv_table.field_names = ["Inventory Type", "Item Count", "Deleted Owners", "Category"]
            
            for inv_type, count, owners in analysis['inventory_type_distribution'][:15]:
                type_name = self.inv_type_mapping.get(inv_type, f"Type {inv_type}")
                category = "Personal" if inv_type in self.personal_inventory_types else "External Storage"
                inv_table.add_row([type_name, self.format_number(count), owners, category])
            print(inv_table)
        
        # Most common orphaned items
        if analysis['common_orphaned_items']:
            print(f"\n🎯 Most Common Orphaned Items:")
            item_table = PrettyTable()
            item_table.field_names = ["Template ID", "Count", "Deleted Owners"]
            
            for template_id, count, owners in analysis['common_orphaned_items'][:10]:
                item_table.add_row([template_id, self.format_number(count), owners])
            print(item_table)
        
        # Additional traces found
        if analysis.get('additional_info'):
            print(f"\n🔗 Traces in Other Tables:")
            for table_col, count in analysis['additional_info'].items():
                print(f"  - {table_col}: {count} references found")
        
        # Recovery possibilities with priority
        recovery = self.generate_recovery_possibilities(analysis)
        if recovery:
            print(f"\n💡 Character Information Recovery Possibilities:")
            for i, possibility in enumerate(recovery, 1):
                priority_icon = "🚨" if possibility.get('priority') == 'HIGH' else "⚠️" if possibility.get('priority') == 'MEDIUM' else "ℹ️"
                print(f"\n{priority_icon} {i}. {possibility['method']}")
                print(f"   {possibility['description']}")
                if 'query' in possibility:
                    print(f"   Query: {possibility['query']}")
                if 'action' in possibility:
                    print(f"   Action: {possibility['action']}")
        
        # NEW: Clean summary of cleanup options
        try:
            cleanup_commands = self.generate_safe_cleanup_commands(analysis)
            print(f"\n🧹 CLEANUP OPTIONS AVAILABLE:")
            for i, cmd in enumerate(cleanup_commands, 1):
                risk_icon = "🚨" if "DANGEROUS" in cmd['title'] else "⚠️" if "MODERATE" in cmd['title'] else "🔒"
                print(f"{risk_icon} {i}. {cmd['title']}")
                print(f"    Impact: {cmd.get('impact', 'Impact not specified')}")
            
            return cleanup_commands  # Return for interactive menu
        except Exception as e:
            print(f"\n❌ Error generating cleanup commands: {e}")
            return []  # Return empty list to prevent further errors

    def export_deleted_characters(self, analysis: Dict, filename: str = None):
        """Export deleted character information to CSV"""
        if not filename:
            filename = f"deleted_characters_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
        try:
            import csv
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Character ID', 'Item Count', 'Inventory Types', 'Unique Items'])
                
                for char in analysis['deleted_characters']:
                    writer.writerow([
                        char['id'],
                        char['item_count'],
                        char['inventory_types'],
                        char['unique_items']
                    ])
                    
            print(f"\n✅ Exported deleted character list to: {filename}")
            return filename
        except Exception as e:
            print(f"\n❌ Export failed: {e}")
            return None
    
    def run_interactive_cleanup_menu(self, analysis: Dict, cleanup_commands: List[Dict]):
        """NEW: Interactive cleanup menu system"""
        if analysis.get('cleanup_damage_detected'):
            print(f"\n❌ Interactive cleanup disabled - damage detected!")
            print(f"Please restore from backup or compensate players first.")
            return
            
        while True:
            print(f"\n" + "="*60)
            print("🧹 INTERACTIVE CLEANUP MENU")
            print("="*60)
            print("Choose a cleanup option to view details and execute:")
            print()
            
            for i, cmd in enumerate(cleanup_commands, 1):
                if cmd.get('warning'):  # Skip damage control option
                    continue
                risk_icon = "🚨" if "DANGEROUS" in cmd['title'] else "⚠️" if "MODERATE" in cmd['title'] else "🔒"
                print(f"{risk_icon} {i}. {cmd['title']}")
            
            print(f"\n0. Return to main menu")
            print(f"="*60)
            
            try:
                choice = input("Enter option number (0 to exit): ").strip()
                
                if choice == "0":
                    break
                    
                choice_num = int(choice)
                if 1 <= choice_num <= len(cleanup_commands):
                    cmd = cleanup_commands[choice_num - 1]
                    
                    if cmd.get('warning'):  # Skip damage control
                        print("❌ This option is not available due to detected damage.")
                        continue
                    
                    self.show_cleanup_details_and_execute(cmd, analysis)
                else:
                    print("❌ Invalid option number.")
                    
            except ValueError:
                print("❌ Please enter a valid number.")
            except KeyboardInterrupt:
                print("\n\n👋 Cleanup menu cancelled.")
                break
    
    def show_cleanup_details_and_execute(self, cmd: Dict, analysis: Dict):
        """NEW: Show cleanup details and offer execution"""
        print(f"\n" + "="*70)
        print(f"📋 CLEANUP OPTION DETAILS")
        print("="*70)
        
        risk_icon = "🚨" if "DANGEROUS" in cmd['title'] else "⚠️" if "MODERATE" in cmd['title'] else "🔒"
        print(f"\n{risk_icon} {cmd['title']}")
        print(f"Description: {cmd['description']}")
        print(f"Impact: {cmd['impact']}")
        
        if cmd.get('warning'):
            print(f"⚠️ WARNING: {cmd['warning']}")
        
        print(f"\nSQL Command:")
        print("-" * 50)
        for line in cmd['sql'].split('\n'):
            print(line)
        print("-" * 50)
        
        # Risk assessment
        if "DANGEROUS" in cmd['title']:
            print(f"\n🚨 HIGH RISK OPERATION")
            print(f"This command will destroy player chest contents!")
            return
        elif "MODERATE" in cmd['title']:
            print(f"\n⚠️ MODERATE RISK OPERATION")
            print(f"Please review the SQL carefully before proceeding.")
        else:
            print(f"\n🔒 LOW RISK OPERATION")
            print(f"This should be safe, but always backup first.")
        
        # Execution options
        print(f"\nOptions:")
        print(f"1. Execute this cleanup now")
        print(f"2. Save SQL to file for manual execution")
        print(f"3. Return to cleanup menu")
        
        while True:
            exec_choice = input("\nChoose option (1-3): ").strip()
            
            if exec_choice == "1":
                self.execute_cleanup_command(cmd, analysis)
                break
            elif exec_choice == "2":
                self.save_cleanup_sql(cmd)
                break
            elif exec_choice == "3":
                break
            else:
                print("Please enter 1, 2, or 3.")
    
    def execute_cleanup_command(self, cmd: Dict, analysis: Dict):
        """NEW: Execute cleanup command with safety checks"""
        print(f"\n⚠️ ABOUT TO EXECUTE CLEANUP COMMAND")
        print(f"Title: {cmd['title']}")
        print(f"Impact: {cmd['impact']}")
        
        # Final confirmation
        print(f"\n🔒 SAFETY CHECKLIST:")
        print(f"✓ Have you backed up your database?")
        print(f"✓ Have you tested this on a backup first?")
        print(f"✓ Are you sure you want to proceed?")
        
        confirm1 = input(f"\nType 'BACKUP DONE' to confirm you have a backup: ").strip()
        if confirm1 != "BACKUP DONE":
            print("❌ Cleanup cancelled - please backup your database first!")
            return
            
        confirm2 = input(f"Type 'EXECUTE' to run the cleanup command: ").strip()
        if confirm2 != "EXECUTE":
            print("❌ Cleanup cancelled.")
            return
        
        print(f"\n🔄 Executing cleanup command...")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Execute the SQL command
            sql_lines = [line.strip() for line in cmd['sql'].split('\n') 
                        if line.strip() and not line.strip().startswith('--')]
            
            total_affected = 0
            for sql_line in sql_lines:
                if sql_line.upper().startswith('DELETE'):
                    cursor.execute(sql_line)
                    affected = cursor.rowcount
                    total_affected += affected
                    print(f"✓ Executed: {affected} rows affected")
            
            conn.commit()
            conn.close()
            
            print(f"\n✅ CLEANUP COMPLETED SUCCESSFULLY!")
            print(f"Total rows affected: {total_affected}")
            print(f"Database has been optimized.")
            
            # Offer to run VACUUM
            vacuum_choice = input(f"\nWould you like to run VACUUM to optimize the database? (y/n): ").strip().lower()
            if vacuum_choice in ['y', 'yes']:
                self.run_vacuum_optimization()
                
        except sqlite3.Error as e:
            print(f"❌ DATABASE ERROR: {e}")
            print(f"Cleanup failed - your database should be unchanged.")
        except Exception as e:
            print(f"❌ UNEXPECTED ERROR: {e}")
            print(f"Please check your database integrity.")
    
    def save_cleanup_sql(self, cmd: Dict):
        """NEW: Save cleanup SQL to file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"conan_cleanup_{timestamp}.sql"
        
        try:
            with open(filename, 'w') as f:
                f.write(f"-- Conan Exiles Database Cleanup Script\n")
                f.write(f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"-- Option: {cmd['title']}\n")
                f.write(f"-- Description: {cmd['description']}\n")
                f.write(f"-- Impact: {cmd['impact']}\n")
                if cmd.get('warning'):
                    f.write(f"-- WARNING: {cmd['warning']}\n")
                f.write(f"\n-- IMPORTANT: Backup your database before running this script!\n")
                f.write(f"-- .backup backup_before_cleanup.db\n\n")
                f.write(cmd['sql'])
                f.write(f"\n\n-- After cleanup, consider running:\n")
                f.write(f"-- VACUUM;\n")
                f.write(f"-- .analyze\n")
            
            print(f"✅ SQL script saved to: {filename}")
            print(f"You can now review and execute it manually.")
            
        except Exception as e:
            print(f"❌ Error saving SQL file: {e}")
    
    def run_main_menu(self, analysis: Dict, cleanup_commands: List[Dict]):
        """NEW: Main menu system for standalone operation"""
        # Main action menu
        if not analysis.get('cleanup_damage_detected'):
            print(f"\n" + "="*60)
            print("🎛️ WHAT WOULD YOU LIKE TO DO?")
            print("="*60)
            print("1. 🧹 Interactive Cleanup Menu")
            print("2. 📤 Export deleted character list to CSV")
            if analysis.get('affected_active_players'):
                print("3. 📤 Export affected players list to CSV")
                print("4. ❌ Exit")
                max_option = 4
            else:
                print("3. ❌ Exit")
                max_option = 3
            
            while True:
                try:
                    choice = input(f"\nEnter your choice (1-{max_option}): ").strip()
                    
                    if choice == "1":
                        # Interactive cleanup menu
                        self.run_interactive_cleanup_menu(analysis, cleanup_commands)
                        break
                    elif choice == "2":
                        # Export deleted characters
                        if 'deleted_characters' in analysis and analysis['deleted_characters']:
                            self.export_deleted_characters(analysis)
                        else:
                            print("No deleted characters to export.")
                        break
                    elif choice == "3":
                        if analysis.get('affected_active_players'):
                            # Export affected players
                            self.export_affected_players(analysis)
                        else:
                            # Exit
                            break
                    elif choice == "4" and max_option == 4:
                        # Exit
                        break
                    else:
                        print(f"❌ Please enter a number between 1 and {max_option}")
                        
                except ValueError:
                    print(f"❌ Please enter a valid number between 1 and {max_option}")
                except KeyboardInterrupt:
                    print("\n\n👋 Goodbye!")
                    break
        else:
            # Damage detected - only offer export options
            print(f"\n⚠️ Due to detected damage, only export options are available:")
            
            export_options = []
            if 'deleted_characters' in analysis and analysis['deleted_characters']:
                export_options.append("Export deleted character list")
            if analysis.get('affected_active_players'):
                export_options.append("Export affected players list")
            
            if export_options:
                for i, option in enumerate(export_options, 1):
                    print(f"{i}. {option}")
                
                while True:
                    try:
                        choice = input(f"\nEnter choice (1-{len(export_options)}, or 0 to exit): ").strip()
                        
                        if choice == "0":
                            break
                        elif choice == "1" and len(export_options) >= 1:
                            if "deleted character" in export_options[0]:
                                self.export_deleted_characters(analysis)
                            else:
                                self.export_affected_players(analysis)
                            break
                        elif choice == "2" and len(export_options) >= 2:
                            self.export_affected_players(analysis)
                            break
                        else:
                            print(f"❌ Please enter a number between 0 and {len(export_options)}")
                            
                    except ValueError:
                        print("❌ Please enter a valid number")
                    except KeyboardInterrupt:
                        print("\n\n👋 Goodbye!")
                        break
            
            # Final safety reminder for damage cases
            print(f"\n" + "⚠️" * 20)
            print("CRITICAL REMINDER:")
            print("- Active players have lost items due to previous cleanup")
            print("- DO NOT run any cleanup commands until damage is addressed")
            print("- Consider restoring from backup or compensating players")
            print("- Use only SAFE cleanup options in the future")
            print("⚠️" * 20)
        """NEW: Run VACUUM to optimize database"""
        print(f"\n🔧 Running VACUUM to optimize database...")
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("VACUUM;")
            conn.close()
            print(f"✅ Database optimization completed.")
        except sqlite3.Error as e:
            print(f"❌ VACUUM failed: {e}")
            print(f"This is usually not critical - your cleanup still worked.")
        """NEW: Export affected active players for compensation tracking"""
        if not analysis.get('affected_active_players'):
            print("No affected active players to export")
            return None
            
        if not filename:
            filename = f"affected_active_players_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
        try:
            import csv
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Character ID', 'Character Name', 'Player ID', 'Items Remaining', 'Status', 'Last Online'])
                
                for player in analysis['affected_active_players']:
                    status = "Missing External Storage" if player['missing_external'] and player['total_items'] > 0 else "All Items Lost"
                    writer.writerow([
                        player['char_id'],
                        player['char_name'],
                        player['player_id'],
                        player['total_items'],
                        status,
                        player.get('last_online', 'Unknown')
                    ])
                    
            print(f"\n✅ Exported affected players list to: {filename}")
            return filename
        except Exception as e:
            print(f"\n❌ Export failed: {e}")
            return None

def run_orphaned_analysis_standalone():
    """Run orphaned analysis as standalone (called from main analyzer)"""
    print("🏛️ Conan Exiles Orphaned Items & Deleted Characters Analyzer")
    print("=" * 60)
    
    db_path = input("Enter the path to game.db: ").strip()
    
    if not os.path.exists(db_path):
        print("❌ Error: Database file not found!")
        return
    
    print(f"\n🔍 Analyzing database: {os.path.basename(db_path)}")
    print("Searching for deleted characters and checking for cleanup damage...")
    
    analyzer = OrphanedItemsAnalyzer(db_path)
    analysis = analyzer.analyze_orphaned_items()
    
    cleanup_commands = analyzer.print_analysis(analysis)
    
    # Run the interactive menu system
    analyzer.run_main_menu(analysis, cleanup_commands)
    
    print(f"\n✅ Analysis complete!")

def run_orphaned_analysis_from_main(db_path: str):
    """Run orphaned analysis when called from main database analyzer (no prompts)"""
    print(f"\n🔍 Running Orphaned Items & Deleted Characters Analysis...")
    print("Searching for deleted characters and checking for cleanup damage...")
    
    analyzer = OrphanedItemsAnalyzer(db_path)
    analysis = analyzer.analyze_orphaned_items()
    
    # Just print analysis, no interactive menu when called from main
    analyzer.print_analysis(analysis)
    
    # Return analysis for main analyzer to handle
    return analysis
    """Main function"""
    print("🏛️ Conan Exiles Orphaned Items & Deleted Characters Analyzer")
    print("=" * 60)
    
    db_path = input("Enter the path to game.db: ").strip()
    
    if not os.path.exists(db_path):
        print("❌ Error: Database file not found!")
        return
    
    print(f"\n🔍 Analyzing database: {os.path.basename(db_path)}")
    print("Searching for deleted characters and checking for cleanup damage...")
    
    analyzer = OrphanedItemsAnalyzer(db_path)
    analysis = analyzer.analyze_orphaned_items()
    
def main():
    """Main function for standalone execution"""
    run_orphaned_analysis_standalone()

if __name__ == "__main__":
    main()
