import sqlite3
import os
from prettytable import PrettyTable
from typing import Dict, Optional
from collections import defaultdict

class ConanExilesInventoryAnalyzer:
    """Specialized analyzer for Conan Exiles item_inventory table"""
    
    # Inventory type mappings (common Conan Exiles inventory types)
    INVENTORY_TYPE_MAPPING = {
        0: "Player Inventory",
        1: "Player Hotbar", 
        2: "Equipment Slots",
        3: "Crafting Queue",
        4: "Large Chest",
        5: "Small Chest",
        6: "Cupboard",
        7: "Armorer's Bench",
        8: "Blacksmith's Bench",
        9: "Carpenter's Bench",
        10: "Tannery",
        11: "Cauldron",
        12: "Firebowl Cauldron",
        13: "Furnace",
        14: "Preservation Box",
        15: "Feed Box",
        16: "Compost Heap",
        17: "Fish Trap",
        18: "Crab Pot",
        19: "Thrall Inventory",
        20: "Pet Inventory",
        21: "Building Piece Storage",
        22: "Vault",
        23: "Map Room",
        24: "Wheel of Pain",
        25: "Torture Rack",
        26: "Altar",
        27: "Stable",
        28: "Animal Pen",
        29: "Placeables Storage",
        30: "Decorative Placeables"
    }
    
    def __init__(self, db_path: str):
        self.db_path = db_path

    @staticmethod
    def format_size(size_in_bytes: float) -> str:
        """Convert bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_in_bytes < 1024:
                return f"{size_in_bytes:.2f} {unit}"
            size_in_bytes /= 1024
        return f"{size_in_bytes:.2f} TB"

    def get_inventory_type_name(self, inv_type: int) -> str:
        """Get human-readable name for inventory type"""
        return self.INVENTORY_TYPE_MAPPING.get(inv_type, f"Unknown Inventory Type {inv_type}")

    def get_player_name_mapping(self) -> Dict[str, str]:
        """Get mapping of owner_id to character names"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if characters table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='characters';")
            if not cursor.fetchone():
                print("⚠️  Warning: 'characters' table not found. Player names will show as IDs.")
                return {}
            
            # Get table structure to find the right columns
            cursor.execute("PRAGMA table_info(characters);")
            columns = cursor.fetchall()
            column_names = [col[1].lower() for col in columns]
            
            # Look for common character name and ID columns
            name_column = None
            id_column = None
            
            for col in ['char_name', 'character_name', 'name', 'player_name']:
                if col in column_names:
                    name_column = col
                    break
                    
            for col in ['id', 'char_id', 'character_id', 'owner_id', 'player_id']:
                if col in column_names:
                    id_column = col
                    break
            
            if not name_column or not id_column:
                print("⚠️  Warning: Could not identify name/ID columns in characters table.")
                return {}
            
            cursor.execute(f"SELECT {id_column}, {name_column} FROM characters WHERE {name_column} IS NOT NULL;")
            results = cursor.fetchall()
            
            conn.close()
            return {str(row[0]): str(row[1]) for row in results}
            
        except Exception as e:
            print(f"⚠️  Error getting player names: {e}")
            return {}

    def analyze_item_inventory(self) -> Dict:
        """Analyze the item_inventory table in detail"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if item_inventory table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='item_inventory';")
            if not cursor.fetchone():
                return {"error": "item_inventory table not found"}
            
            # Get table structure
            cursor.execute("PRAGMA table_info(item_inventory);")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            print(f"📋 Item Inventory Table Columns: {', '.join(column_names)}")
            
            # Verify required columns exist
            required_columns = ['owner_id', 'inv_type', 'template_id']
            missing_columns = [col for col in required_columns if col not in column_names]
            if missing_columns:
                return {"error": f"Missing required columns: {missing_columns}"}
            
            # Get total item count
            cursor.execute("SELECT COUNT(*) FROM item_inventory;")
            total_items = cursor.fetchone()[0]
            
            # Get player name mapping
            player_names = self.get_player_name_mapping()
            
            # Analyze by owner_id (players)
            cursor.execute("""
                SELECT owner_id, COUNT(*) as item_count, 
                       GROUP_CONCAT(DISTINCT inv_type) as inv_types,
                       COUNT(DISTINCT inv_type) as unique_inv_types
                FROM item_inventory 
                WHERE owner_id IS NOT NULL 
                GROUP BY owner_id 
                ORDER BY item_count DESC
            """)
            player_stats = cursor.fetchall()
            
            # Analyze by inventory type
            cursor.execute("""
                SELECT inv_type, COUNT(*) as item_count,
                       COUNT(DISTINCT owner_id) as unique_owners,
                       COUNT(DISTINCT template_id) as unique_items
                FROM item_inventory 
                GROUP BY inv_type 
                ORDER BY item_count DESC
            """)
            inventory_type_stats = cursor.fetchall()
            
            # Analyze most common items
            cursor.execute("""
                SELECT template_id, COUNT(*) as item_count,
                       COUNT(DISTINCT owner_id) as owners_with_item
                FROM item_inventory 
                GROUP BY template_id 
                ORDER BY item_count DESC 
                LIMIT 20
            """)
            popular_items = cursor.fetchall()
            
            # Get sample data for size estimation
            cursor.execute("SELECT * FROM item_inventory LIMIT 100;")
            sample_rows = cursor.fetchall()
            avg_row_size = sum(len(str(row)) for row in sample_rows) / len(sample_rows) if sample_rows else 0
            
            analysis = {
                "total_items": total_items,
                "columns": column_names,
                "player_stats": player_stats,
                "inventory_type_stats": inventory_type_stats,
                "popular_items": popular_items,
                "player_names": player_names,
                "avg_row_size": avg_row_size,
                "estimated_table_size": avg_row_size * total_items
            }
            
            conn.close()
            return analysis
            
        except sqlite3.Error as e:
            return {"error": f"SQLite error: {e}"}
        except Exception as e:
            return {"error": f"Error: {e}"}

    def print_inventory_analysis(self, analysis: Dict) -> None:
        """Print detailed analysis of item_inventory table"""
        if "error" in analysis:
            print(f"\n❌ Inventory Analysis Error: {analysis['error']}")
            return
        
        print("\n" + "="*100)
        print("🎒 CONAN EXILES INVENTORY ANALYSIS")
        print("="*100)
        
        print(f"\n📊 Overview:")
        print(f"Total Items in Database: {analysis['total_items']:,}")
        print(f"Estimated Table Size: {self.format_size(analysis['estimated_table_size'])}")
        print(f"Average Row Size: {analysis['avg_row_size']:.1f} bytes")
        
        # Player inventory analysis
        if analysis['player_stats']:
            print(f"\n👥 TOP PLAYERS BY ITEM COUNT:")
            print("="*100)
            
            player_table = PrettyTable()
            player_table.field_names = ["Rank", "Player ID", "Player Name", "Item Count", "Inventory Types", "Percentage", "Est. Size Impact"]
            player_table.align["Player ID"] = "l"
            player_table.align["Player Name"] = "l"  
            player_table.align["Item Count"] = "r"
            player_table.align["Inventory Types"] = "l"
            player_table.align["Percentage"] = "r"
            player_table.align["Est. Size Impact"] = "r"
            
            total_items = analysis['total_items']
            avg_row_size = analysis['avg_row_size']
            player_names = analysis['player_names']
            
            for rank, (owner_id, item_count, inv_types_str, unique_inv_types) in enumerate(analysis['player_stats'][:25], 1):
                player_name = player_names.get(str(owner_id), "Unknown Player")
                percentage = (item_count / total_items) * 100 if total_items > 0 else 0
                size_impact = item_count * avg_row_size
                
                # Parse inventory types
                if inv_types_str:
                    inv_type_ids = [int(x.strip()) for x in inv_types_str.split(',') if x.strip().isdigit()]
                    inv_type_names = [self.get_inventory_type_name(inv_id) for inv_id in inv_type_ids[:3]]  # Show first 3
                    inv_types_display = ', '.join(inv_type_names)
                    if len(inv_type_ids) > 3:
                        inv_types_display += f" (+{len(inv_type_ids)-3} more)"
                else:
                    inv_types_display = "Unknown"
                
                player_table.add_row([
                    rank,
                    str(owner_id)[:20],  # Truncate long IDs
                    player_name[:25],    # Truncate long names
                    f"{item_count:,}",
                    inv_types_display[:35],  # Truncate long inventory lists
                    f"{percentage:.2f}%",
                    self.format_size(size_impact)
                ])
            
            print(player_table)
        
        # Inventory type analysis
        if analysis['inventory_type_stats']:
            print(f"\n📦 INVENTORY TYPE ANALYSIS:")
            print("="*80)
            
            inv_table = PrettyTable()
            inv_table.field_names = ["Inventory Type", "Item Count", "Unique Owners", "Unique Items", "Percentage"]
            inv_table.align["Inventory Type"] = "l"
            inv_table.align["Item Count"] = "r"
            inv_table.align["Unique Owners"] = "r"
            inv_table.align["Unique Items"] = "r"
            inv_table.align["Percentage"] = "r"
            
            total_items = analysis['total_items']
            
            for inv_type, item_count, unique_owners, unique_items in analysis['inventory_type_stats']:
                inv_type_name = self.get_inventory_type_name(inv_type)
                percentage = (item_count / total_items) * 100 if total_items > 0 else 0
                
                inv_table.add_row([
                    inv_type_name[:30],
                    f"{item_count:,}",
                    f"{unique_owners:,}",
                    f"{unique_items:,}",
                    f"{percentage:.1f}%"
                ])
            
            print(inv_table)
        
        # Popular items analysis
        if analysis['popular_items']:
            print(f"\n🔥 MOST COMMON ITEMS:")
            print("="*60)
            
            items_table = PrettyTable()
            items_table.field_names = ["Rank", "Template ID", "Item Count", "Players with Item", "Percentage"]
            items_table.align["Template ID"] = "l"
            items_table.align["Item Count"] = "r"
            items_table.align["Players with Item"] = "r"
            items_table.align["Percentage"] = "r"
            
            total_items = analysis['total_items']
            
            for rank, (template_id, item_count, owners_with_item) in enumerate(analysis['popular_items'][:15], 1):
                percentage = (item_count / total_items) * 100 if total_items > 0 else 0
                
                items_table.add_row([
                    rank,
                    str(template_id)[:25],
                    f"{item_count:,}",
                    f"{owners_with_item:,}",
                    f"{percentage:.2f}%"
                ])
            
            print(items_table)
        
        # Recommendations
        print(f"\n💡 INVENTORY ANALYSIS RECOMMENDATIONS:")
        print("="*50)
        
        if analysis['player_stats']:
            top_player = analysis['player_stats'][0]
            top_player_items = top_player[1]
            top_player_percentage = (top_player_items / analysis['total_items']) * 100
            
            if top_player_percentage > 10:
                player_name = analysis['player_names'].get(str(top_player[0]), "Unknown")
                print(f"⚠️  Player '{player_name}' owns {top_player_percentage:.1f}% of all items ({top_player_items:,} items)")
                print("   Consider investigating for potential item duplication or hoarding")
        
        if analysis['inventory_type_stats']:
            # Find the inventory type with most items
            top_inv_type = analysis['inventory_type_stats'][0]
            inv_type_name = self.get_inventory_type_name(top_inv_type[0])
            inv_percentage = (top_inv_type[1] / analysis['total_items']) * 100
            
            print(f"📦 '{inv_type_name}' contains {inv_percentage:.1f}% of all items")
            
            if inv_percentage > 50:
                print("   High concentration in one inventory type - consider if this is expected")
        
        print(f"\n🔧 Maintenance Suggestions:")
        print("- Regular cleanup of abandoned player inventories")
        print("- Monitor for unusual item accumulation patterns")  
        print("- Consider archiving inventories of inactive players")
        print("- Use VACUUM command after large cleanups to reclaim space")
        
        if analysis['total_items'] > 500000:
            print("⚠️  High item count - consider implementing automated cleanup policies")

    def run_analysis(self) -> None:
        """Run the complete inventory analysis"""
        print("🔍 Analyzing item_inventory table...")
        
        # Focus on inventory analysis
        inventory_analysis = self.analyze_item_inventory()
        self.print_inventory_analysis(inventory_analysis)
        
        # Basic database info
        try:
            actual_file_size = os.path.getsize(self.db_path)
            print(f"\n📏 Database File Size: {self.format_size(actual_file_size)}")
        except:
            print("\n📏 Could not determine database file size")

def main():
    """Main function for standalone execution"""
    print("🏛️ Conan Exiles Database Analyzer - Inventory Focus")
    print("=" * 60)
    
    db_path = input("Enter the path to game.db: ").strip()
    
    if not os.path.exists(db_path):
        print("❌ Error: Database file not found!")
        return
    
    print(f"\n🔍 Analyzing database: {os.path.basename(db_path)}")
    print("Focusing on item_inventory analysis...")
    print("Please wait...")
    
    analyzer = ConanExilesInventoryAnalyzer(db_path)
    analyzer.run_analysis()
    
    print(f"\n✅ Inventory analysis complete!")

if __name__ == "__main__":
    main()