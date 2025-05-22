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
            
            # Find all unique owner_ids from item_inventory
            cursor.execute("SELECT DISTINCT owner_id FROM item_inventory WHERE owner_id IS NOT NULL")
            all_owner_ids = set(row[0] for row in cursor.fetchall())
            
            # Calculate deleted character IDs
            deleted_char_ids = all_owner_ids - existing_chars
            
            # Analyze orphaned items by deleted character
            orphaned_analysis = {}
            
            # Get detailed info for each deleted character
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
            
            # Get inventory type distribution for orphaned items
            cursor.execute("""
                SELECT 
                    inv_type,
                    COUNT(*) as count,
                    COUNT(DISTINCT owner_id) as unique_owners
                FROM item_inventory
                WHERE owner_id NOT IN (SELECT id FROM {})
                GROUP BY inv_type
                ORDER BY count DESC
            """.format(char_table_name))
            inv_type_distribution = cursor.fetchall()
            
            # Get most common orphaned items
            cursor.execute("""
                SELECT 
                    template_id,
                    COUNT(*) as count,
                    COUNT(DISTINCT owner_id) as unique_owners
                FROM item_inventory
                WHERE owner_id NOT IN (SELECT id FROM {})
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
                'char_table_name': char_table_name
            }
            
        except Exception as e:
            return {"error": f"Analysis error: {e}"}
    
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
        
        if analysis.get('additional_info'):
            possibilities.append({
                'method': 'Check game_events table',
                'description': 'Game events might contain character names or actions',
                'query': "SELECT DISTINCT player_id, COUNT(*) FROM game_events WHERE player_id IN (deleted_ids) GROUP BY player_id"
            })
            
        if analysis.get('id_ranges', {}).get('appears_sequential'):
            possibilities.append({
                'method': 'Mass deletion detected',
                'description': 'Sequential ID ranges suggest mass deletion event (wipe, cleanup, or migration)',
                'action': 'Check server logs around deletion time'
            })
            
        possibilities.append({
            'method': 'Check backup databases',
            'description': 'Older backup files might contain character information',
            'action': 'Compare with backup game.db files if available'
        })
        
        return possibilities
    
    def print_analysis(self, analysis: Dict):
        """Print the orphaned items analysis"""
        if "error" in analysis:
            print(f"\n❌ Error: {analysis['error']}")
            return
            
        print("\n" + "="*80)
        print("🔍 ORPHANED ITEMS & DELETED CHARACTERS ANALYSIS")
        print("="*80)
        
        print(f"\n📊 Summary:")
        print(f"Existing Characters: {self.format_number(analysis['existing_characters'])}")
        print(f"Deleted Character IDs: {self.format_number(analysis['total_deleted_characters'])} (includes respawns, resets, etc.)")
        print(f"Total Orphaned Items: {self.format_number(analysis['total_orphaned_items'])}")
        print(f"Character Table: {analysis['char_table_name']}")
        
        # Deletion percentage
        total_chars = analysis['existing_characters'] + analysis['total_deleted_characters']
        deletion_rate = (analysis['total_deleted_characters'] / total_chars * 100) if total_chars > 0 else 0
        print(f"Character ID Turnover: {deletion_rate:.1f}% of all character IDs ever created")
        print(f"💡 Note: Deleted Character IDs ≠ Unique Players Lost")
        print(f"   Many IDs come from character respawns, resets, and server maintenance")
        
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
        
        # Inventory type distribution
        if analysis['inventory_type_distribution']:
            print(f"\n📦 Orphaned Items by Inventory Type:")
            inv_table = PrettyTable()
            inv_table.field_names = ["Inventory Type", "Item Count", "Deleted Owners"]
            
            # Map common inventory types
            inv_type_names = {
                0: "Player Inventory",
                1: "Player Hotbar",
                2: "Equipment Slots",
                4: "Large Chest",
                5: "Small Chest",
                7: "Armorer's Bench",
                8: "Blacksmith's Bench",
                22: "Vault"
            }
            
            for inv_type, count, owners in analysis['inventory_type_distribution'][:10]:
                type_name = inv_type_names.get(inv_type, f"Type {inv_type}")
                inv_table.add_row([type_name, self.format_number(count), owners])
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
        
        # Recovery possibilities
        recovery = self.generate_recovery_possibilities(analysis)
        if recovery:
            print(f"\n💡 Character Information Recovery Possibilities:")
            for i, possibility in enumerate(recovery, 1):
                print(f"\n{i}. {possibility['method']}")
                print(f"   {possibility['description']}")
                if 'query' in possibility:
                    print(f"   Query: {possibility['query']}")
                if 'action' in possibility:
                    print(f"   Action: {possibility['action']}")
        
        # Cleanup command
        print(f"\n🧹 Cleanup Command:")
        print(f"DELETE FROM item_inventory WHERE owner_id NOT IN (SELECT id FROM {analysis['char_table_name']});")
        print(f"This will remove {self.format_number(analysis['total_orphaned_items'])} orphaned items")
        
        # Export option
        print(f"\n📤 Export Options:")
        print("The list of deleted character IDs can be exported for further investigation")

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

def main():
    """Main function"""
    print("🏛️ Conan Exiles Orphaned Items & Deleted Characters Analyzer")
    print("=" * 60)
    
    db_path = input("Enter the path to game.db: ").strip()
    
    if not os.path.exists(db_path):
        print("❌ Error: Database file not found!")
        return
    
    print(f"\n🔍 Analyzing database: {os.path.basename(db_path)}")
    print("Searching for deleted characters based on orphaned items...")
    
    analyzer = OrphanedItemsAnalyzer(db_path)
    analysis = analyzer.analyze_orphaned_items()
    
    analyzer.print_analysis(analysis)
    
    if 'deleted_characters' in analysis and analysis['deleted_characters']:
        export = input("\nWould you like to export the deleted character list to CSV? (y/n): ").strip().lower()
        if export in ['y', 'yes']:
            analyzer.export_deleted_characters(analysis)
    
    print(f"\n✅ Analysis complete!")

if __name__ == "__main__":
    main()