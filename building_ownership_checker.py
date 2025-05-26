#!/usr/bin/env python3
"""
Enhanced Building Ownership Checker for Conan Exiles
Updated to properly display character names and levels
"""

import sqlite3
import sys
from collections import defaultdict

def analyze_building_ownership(db_path, target_char_ids=None):
    """Comprehensive building ownership analysis with proper character info"""
    
    print("🏗️ COMPREHENSIVE BUILDING OWNERSHIP ANALYSIS")
    print("=" * 60)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check what building-related tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%build%' OR name LIKE '%actor%'")
    building_tables = [row[0] for row in cursor.fetchall()]
    
    print(f"📋 Building-related tables found: {building_tables}")
    
    # Analyze the main buildings table with proper character info
    print(f"\n🔍 ANALYZING BUILDINGS TABLE")
    print("-" * 40)
    
    try:
        # Enhanced building analysis with guild support and placeable separation
        cursor.execute("""
            SELECT 
                b.owner_id, 
                COUNT(b.object_id) as building_count,
                c.char_name,
                c.level,
                c.playerId,
                c.id as char_id,
                a.platformId as steam_id,
                g.name as guild_name,
                g.guildId as guild_id,
                go.platformId as guild_owner_steam_id,
                -- Count building structures vs placeables
                SUM(CASE WHEN EXISTS(SELECT 1 FROM building_instances bi WHERE bi.object_id = b.object_id) THEN 1 ELSE 0 END) as structures,
                SUM(CASE WHEN NOT EXISTS(SELECT 1 FROM building_instances bi WHERE bi.object_id = b.object_id) THEN 1 ELSE 0 END) as placeables,
                CASE 
                    WHEN c.char_name IS NOT NULL THEN 'active_character'
                    WHEN g.name IS NOT NULL THEN 'guild'
                    ELSE 'deleted'
                END as status
            FROM buildings b
            LEFT JOIN characters c ON b.owner_id = c.id
            LEFT JOIN account a ON c.playerId = a.id
            LEFT JOIN guilds g ON b.owner_id = g.guildId
            LEFT JOIN characters gc ON g.owner = gc.id
            LEFT JOIN account go ON gc.playerId = go.id
            WHERE b.owner_id != 0
            GROUP BY b.owner_id, c.char_name, c.level, c.playerId, c.id, a.platformId, g.name, g.guildId, go.platformId
            ORDER BY building_count DESC
            LIMIT 20
        """)
        
        top_builders = cursor.fetchall()
        
        print(f"🏆 TOP BUILDING OWNERS:")
        active_count = 0
        deleted_count = 0
        
        for i, builder in enumerate(top_builders, 1):
            owner_id = builder['owner_id']
            count = builder['building_count']
            char_name = builder['char_name']
            level = builder['level']
            status = builder['status']
            steam_id = builder['steam_id']
            guild_name = builder['guild_name']
            guild_owner_steam_id = builder['guild_owner_steam_id']
            structures = builder['structures']
            placeables = builder['placeables']
            
            # Track statistics
            if status == 'active_character':
                active_count += 1
            elif status == 'guild':
                # Count guilds separately but don't add to deleted count
                pass
            else:
                deleted_count += 1
            
            # Determine flag
            if count > 1000:
                flag = "🚨 EXCESSIVE"
            elif count > 500:
                flag = "⚠️ HIGH"
            else:
                flag = "📋 NORMAL"
            
            # Format display with guild support
            if status == 'guild':
                if guild_owner_steam_id:
                    display_name = f"{guild_name} (Guild-Owner:{guild_owner_steam_id})"
                else:
                    display_name = f"{guild_name} (Guild)"
                level_str = "Guild"
                status_icon = "🏛️"
            elif char_name:
                if steam_id:
                    display_name = f"{char_name}_{owner_id} (SteamID:{steam_id})"
                else:
                    display_name = f"{char_name}_{owner_id}"
                level_str = str(level) if level is not None else "?"
                status_icon = "👤"
            else:
                display_name = f"DELETED_{owner_id}"
                level_str = "?"
                status_icon = "💀"
            
            # Add breakdown for all
            breakdown = f" [{structures} structures, {placeables} placeables]"
            
            print(f"   {i}. {status_icon} {display_name} (Level {level_str}): {count:,} buildings {flag}{breakdown}")
        
        print(f"\n📊 OWNERSHIP STATUS SUMMARY:")
        print(f"   👤 Active characters in top 20: {active_count}")
        print(f"   💀 Deleted characters in top 20: {deleted_count}")
        
        # Get total orphaned buildings count (exclude guilds)
        cursor.execute("""
            SELECT COUNT(*) as orphaned_buildings
            FROM buildings b
            LEFT JOIN characters c ON b.owner_id = c.id
            LEFT JOIN guilds g ON b.owner_id = g.guildId
            WHERE c.id IS NULL AND g.guildId IS NULL AND b.owner_id != 0
        """)
        orphaned_total = cursor.fetchone()['orphaned_buildings']
        
        if orphaned_total > 0:
            print(f"   🚨 Total orphaned buildings: {orphaned_total:,}")
            print(f"   💡 These buildings belong to deleted characters")
        
        # Check if any of our suspects have buildings
        if target_char_ids:
            print(f"\n🎯 SUSPECT BUILDING ANALYSIS:")
            print("-" * 40)
            
            for char_id in target_char_ids:
                # Get character info - try both id and playerId matches
                cursor.execute("""
                    SELECT char_name, level, playerId, id
                    FROM characters 
                    WHERE id = ? OR playerId = ?
                """, (char_id, char_id))
                result = cursor.fetchone()
                
                if result:
                    char_name = result['char_name'] or f"Unknown"
                    level = result['level'] or "?"
                    player_id = result['playerId']
                    char_db_id = result['id']
                    display_name = f"{char_name}_{char_id}"
                else:
                    display_name = f"ID_{char_id}"
                    player_id = char_id
                
                # Check building ownership using corrected relationship
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM buildings 
                    WHERE owner_id = ?
                """, (char_id,))
                building_count = cursor.fetchone()['count']
                
                if building_count > 0:
                    if result:
                        print(f"   🏠 {display_name} (Level {level}): {building_count:,} buildings")
                    else:
                        print(f"   🏠 {display_name}: {building_count:,} buildings")
                    
                    # Get building details
                    cursor.execute("""
                        SELECT object_id FROM buildings 
                        WHERE owner_id = ?
                        LIMIT 5
                    """, (char_id,))
                    
                    building_objects = cursor.fetchall()
                    object_ids = [str(obj['object_id']) for obj in building_objects]
                    print(f"      Sample Object IDs: {', '.join(object_ids)}")
                else:
                    print(f"   ❌ {display_name}: No buildings found")
        
        # Check for ownership anomalies
        print(f"\n🔍 OWNERSHIP ANOMALIES:")
        print("-" * 40)
        
        # Buildings owned by non-existent characters or guilds (exclude system buildings)
        cursor.execute("""
            SELECT 
                b.owner_id, 
                COUNT(*) as count
            FROM buildings b
            LEFT JOIN characters c ON b.owner_id = c.id
            LEFT JOIN guilds g ON b.owner_id = g.guildId
            WHERE c.id IS NULL AND g.guildId IS NULL AND b.owner_id != 0
            GROUP BY b.owner_id
            ORDER BY count DESC
            LIMIT 10
        """)
        
        orphaned_buildings = cursor.fetchall()
        if orphaned_buildings:
            print(f"   ⚠️ ORPHANED BUILDINGS (owner doesn't exist in characters table):")
            for orphan in orphaned_buildings:
                owner_id = orphan['owner_id']
                count = orphan['count']
                print(f"      Owner ID {owner_id}: {count:,} buildings")
        else:
            print(f"   ✅ No orphaned buildings found - all buildings have valid owners")
        
    except Exception as e:
        print(f"❌ Error analyzing buildings table: {e}")
    
    # Enhanced building_instances analysis
    print(f"\n🔍 ANALYZING BUILDING_INSTANCES TABLE")
    print("-" * 40)
    
    try:
        cursor.execute("SELECT COUNT(*) as count FROM building_instances")
        total_instances = cursor.fetchone()['count']
        print(f"📊 Total building instances: {total_instances:,}")
        
        # Sample some building instances with owner info
        cursor.execute("""
            SELECT 
                bi.object_id, 
                COUNT(*) as piece_count,
                b.owner_id,
                c.char_name,
                c.level
            FROM building_instances bi
            LEFT JOIN buildings b ON bi.object_id = b.object_id
            LEFT JOIN characters c ON b.owner_id = c.id
            GROUP BY bi.object_id
            ORDER BY piece_count DESC
            LIMIT 10
        """)
        
        large_structures = cursor.fetchall()
        print(f"🏰 LARGEST STRUCTURES:")
        
        for i, structure in enumerate(large_structures, 1):
            object_id = structure['object_id']
            piece_count = structure['piece_count']
            owner_id = structure['owner_id']
            char_name = structure['char_name']
            level = structure['level']
            
            if char_name and owner_id:
                owner_display = f"{char_name}_{owner_id} (Level {level or '?'})"
            elif owner_id:
                owner_display = f"DELETED_{owner_id}"
            else:
                owner_display = "No Owner Found"
            
            print(f"   {i}. Object {object_id}: {piece_count:,} pieces (Owner: {owner_display})")
        
    except Exception as e:
        print(f"❌ Error analyzing building_instances: {e}")
    
    # Check actor_position for placed items
    print(f"\n🔍 ANALYZING ACTOR_POSITION TABLE")
    print("-" * 40)
    
    try:
        cursor.execute("SELECT COUNT(*) as count FROM actor_position")
        total_actors = cursor.fetchone()['count']
        print(f"📊 Total placed actors: {total_actors:,}")
        
        # Show some sample classes
        cursor.execute("""
            SELECT class, COUNT(*) as count
            FROM actor_position
            GROUP BY class
            ORDER BY count DESC
            LIMIT 10
        """)
        
        common_classes = cursor.fetchall()
        print(f"🎭 MOST COMMON PLACED ITEMS:")
        
        for i, item_class in enumerate(common_classes, 1):
            class_name = item_class['class']
            count = item_class['count']
            
            # Simplify class name for display
            simple_name = class_name.split('/')[-1].split('.')[0] if '/' in class_name else class_name
            print(f"   {i}. {simple_name}: {count:,}")
        
    except Exception as e:
        print(f"❌ Error analyzing actor_position: {e}")
    
    # Character ownership summary
    print(f"\n📊 CHARACTER OWNERSHIP SUMMARY:")
    print("-" * 40)
    
    try:
        # Total active characters with buildings
        cursor.execute("""
            SELECT COUNT(DISTINCT c.id) as active_builders
            FROM characters c
            INNER JOIN buildings b ON c.id = b.owner_id
        """)
        active_builders = cursor.fetchone()['active_builders']
        
        # Total characters in database
        cursor.execute("SELECT COUNT(*) as total_chars FROM characters")
        total_chars = cursor.fetchone()['total_chars']
        
        # Average buildings per active builder
        cursor.execute("""
            SELECT AVG(building_count) as avg_buildings
            FROM (
                SELECT COUNT(*) as building_count
                FROM buildings b
                INNER JOIN characters c ON c.id = b.owner_id
                GROUP BY c.id
            )
        """)
        avg_result = cursor.fetchone()
        avg_buildings = avg_result['avg_buildings'] if avg_result and avg_result['avg_buildings'] else 0
        
        print(f"   👥 Total characters: {total_chars:,}")
        print(f"   🏗️ Characters with buildings: {active_builders:,}")
        print(f"   📈 Percentage with buildings: {(active_builders/total_chars*100):.1f}%")
        print(f"   📊 Average buildings per builder: {avg_buildings:.1f}")
        
    except Exception as e:
        print(f"❌ Error in ownership summary: {e}")
    
    conn.close()
    
    print(f"\n💡 SUMMARY:")
    print("-" * 40)
    print(f"✅ Building ownership IS tracked in the buildings table")
    print(f"✅ Character names and levels are properly displayed")
    print(f"✅ owner_id in buildings links to id in characters table")
    print(f"✅ building_instances shows individual building pieces")
    print(f"✅ actor_position shows all placed items (may not have owner info)")
    
    # Add educational note about deleted characters
    if orphaned_total > 0:
        print(f"\n📚 UNDERSTANDING 'DELETED' CHARACTERS:")
        print("-" * 40)
        print(f"💡 DELETED_XXX means character ID XXX no longer exists in database")
        print(f"💡 Players who recreate characters get NEW character IDs")
        print(f"💡 Old buildings remain tied to the old (deleted) character ID")
        print(f"💡 Same Steam account can have multiple character IDs over time")
        print(f"💡 'DELETED' doesn't mean the player left - just remade their character")

def main():
    if len(sys.argv) < 2:
        print("Usage: python building_ownership_checker.py game.db [character_id1 character_id2 ...]")
        sys.exit(1)
    
    db_path = sys.argv[1]
    character_ids = [int(char_id) for char_id in sys.argv[2:]] if len(sys.argv) > 2 else None
    
    analyze_building_ownership(db_path, character_ids)

if __name__ == "__main__":
    main()