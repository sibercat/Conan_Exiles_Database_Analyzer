import sqlite3
import os
import subprocess
from prettytable import PrettyTable
from typing import Tuple, List, Dict, Optional
from collections import Counter
from datetime import datetime

# Try to import the specialized analyzers
try:
    from SQLite_Item_table import ConanExilesInventoryAnalyzer
    INVENTORY_ANALYZER_AVAILABLE = True
except ImportError:
    INVENTORY_ANALYZER_AVAILABLE = False

try:
    from SQLite_Game_Events import ConanExilesGameEventsAnalyzer
    GAME_EVENTS_ANALYZER_AVAILABLE = True
except ImportError:
    GAME_EVENTS_ANALYZER_AVAILABLE = False

class ConanExilesDBAnalyzer:
    """Core database analyzer for general structure and health analysis"""
    
    # Size thresholds in bytes
    WARNING_SIZE = 730 * 1024 * 1024  # 730MB
    CRITICAL_SIZE = 1024 * 1024 * 1024  # 1GB
    
    def __init__(self, db_path: str, sqlite_exe_path: Optional[str] = None):
        self.db_path = db_path
        self.sqlite_exe_path = sqlite_exe_path

    @staticmethod
    def format_size(size_in_bytes: float) -> str:
        """Convert bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_in_bytes < 1024:
                return f"{size_in_bytes:.2f} {unit}"
            size_in_bytes /= 1024
        return f"{size_in_bytes:.2f} TB"

    def get_size_warning(self, size: int) -> str:
        """Generate size warning message based on database size"""
        warnings = []
        
        if size >= self.CRITICAL_SIZE:
            warnings.append("\n⚠️ CRITICAL SIZE WARNING:")
            warnings.append("- Database size exceeds 1GB")
            warnings.append("- Large databases may cause server performance issues")
            warnings.append("- Consider archiving old data or cleaning up unused entries")
            warnings.append("- Regular database maintenance is strongly recommended")
            warnings.append("- Monitor server performance closely")
        elif size >= self.WARNING_SIZE:
            warnings.append("\n⚠️ SIZE WARNING:")
            warnings.append("- Database size exceeds 730MB")
            warnings.append("- Consider implementing regular maintenance")
            warnings.append("- Monitor for performance impact")
            warnings.append("- Check for unnecessary data accumulation")
        
        if warnings:
            warnings.extend([
                "\nRecommended actions:",
                "1. Backup your database before any maintenance",
                "2. Consider cleaning old game events (especially high-frequency events)",
                "3. Remove data for long-inactive players",
                "4. Archive or clean up old building data",
                "5. Optimize database using VACUUM command"
            ])
        
        return "\n".join(warnings)

    def get_file_size(self) -> int:
        """Get actual file size from the filesystem"""
        try:
            return os.path.getsize(self.db_path)
        except OSError as e:
            print(f"Error getting file size: {e}")
            return 0

    def run_sqlite_command(self, command: str) -> str:
        """Execute SQLite command using specified sqlite3.exe"""
        if not self.sqlite_exe_path:
            return ""
            
        try:
            process = subprocess.Popen(
                [self.sqlite_exe_path, self.db_path, command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            output, error = process.communicate()
            if error and not error.isspace():
                print(f"SQLite Error: {error}")
            return output.strip()
        except Exception as e:
            print(f"Error executing sqlite3: {e}")
            return ""

    def get_fragmentation_info(self) -> Dict[str, int]:
        """Get database fragmentation information"""
        if not self.sqlite_exe_path:
            return {'freelist_count': 0, 'page_count': 0, 'page_size': 0}
            
        return {
            'freelist_count': int(self.run_sqlite_command("PRAGMA freelist_count;") or 0),
            'page_count': int(self.run_sqlite_command("PRAGMA page_count;") or 0),
            'page_size': int(self.run_sqlite_command("PRAGMA page_size;") or 0)
        }

    def analyze_tables(self) -> Tuple[List[Dict], int]:
        """Analyze database tables and return their sizes"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            table_info = []
            
            for table in tables:
                table_name = table[0]
                
                cursor.execute(f"SELECT COUNT(*) FROM '{table_name}';")
                row_count = cursor.fetchone()[0]
                
                cursor.execute(f"PRAGMA table_info('{table_name}');")
                columns = cursor.fetchall()
                
                cursor.execute(f"PRAGMA index_list('{table_name}');")
                indexes = cursor.fetchall()
                
                cursor.execute(f"SELECT * FROM '{table_name}' LIMIT 1;")
                row = cursor.fetchone()
                row_size = sum(len(str(field)) for field in row) if row else 0
                
                table_info.append({
                    'name': table_name,
                    'rows': row_count,
                    'columns': len(columns),
                    'indexes': len(indexes),
                    'estimated_size': row_size * row_count
                })
            
            cursor.execute("PRAGMA page_size;")
            page_size = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_count;")
            page_count = cursor.fetchone()[0]
            
            conn.close()
            
            return sorted(table_info, key=lambda x: x['estimated_size'], reverse=True), page_size * page_count
            
        except sqlite3.Error as e:
            print(f"SQLite error: {e}")
            return [], 0
        except Exception as e:
            print(f"Error: {e}")
            return [], 0

    def generate_general_report(self) -> None:
        """Generate and print general database structure analysis report"""
        table_info, sqlite_size = self.analyze_tables()
        actual_file_size = self.get_file_size()
        frag_info = self.get_fragmentation_info() if self.sqlite_exe_path else None
        
        if not table_info:
            print("No tables found or error occurred!")
            return
        
        print("\n" + "="*80)
        print("📋 GENERAL DATABASE STRUCTURE ANALYSIS")
        print("="*80)
        
        pt = PrettyTable()
        pt.field_names = ["Table Name", "Rows", "Columns", "Indexes", "Estimated Data Size"]
        pt.align["Table Name"] = "l"
        pt.align["Estimated Data Size"] = "r"
        
        total_estimated_size = 0
        for table in table_info:
            pt.add_row([
                table['name'],
                f"{table['rows']:,}",
                table['columns'],
                table['indexes'],
                self.format_size(table['estimated_size'])
            ])
            total_estimated_size += table['estimated_size']
            
        print(pt)
        print("\n📏 Size Analysis:")
        print(f"Total estimated data size: {self.format_size(total_estimated_size)}")
        print(f"SQLite reported size: {self.format_size(sqlite_size)}")
        print(f"Actual file size: {self.format_size(actual_file_size)}")
        
        overhead = actual_file_size - total_estimated_size
        overhead_percentage = (overhead / actual_file_size) * 100 if actual_file_size > 0 else 0
        print(f"\nDatabase overhead: {self.format_size(overhead)} ({overhead_percentage:.1f}% of file size)")
        
        # Print size warnings if applicable
        print(self.get_size_warning(actual_file_size))
        
        if frag_info and frag_info['page_count'] > 0:
            free_pages = frag_info['freelist_count']
            total_pages = frag_info['page_count']
            page_size = frag_info['page_size']
            free_space = free_pages * page_size
            frag_percentage = (free_pages / total_pages * 100)
            
            print("\n🔧 Fragmentation Analysis:")
            print(f"Page Size: {self.format_size(page_size)}")
            print(f"Total Pages: {total_pages:,}")
            print(f"Free Pages: {free_pages:,}")
            print(f"Free Space: {self.format_size(free_space)}")
            print(f"Fragmentation: {frag_percentage:.1f}%")
            
            if frag_percentage > 20:
                print("⚠️  High fragmentation detected - consider running VACUUM")
        
        print("\n💡 General Maintenance Recommendations:")
        print("- Regular database backups before maintenance")
        print("- Monitor table growth trends")
        print("- Use specialized analyzers for detailed table analysis")
        print("- Consider VACUUM command if fragmentation is high")
        print("\nNote: Overhead includes indexes, free space, SQLite page structures, and other metadata")

def show_main_menu():
    """Display the main menu options"""
    print("\n" + "="*70)
    print("🏛️ CONAN EXILES DATABASE ANALYZER SUITE - By: Sibercat")
    print("="*70)
    print("Choose an analysis option:")
    print()
    
    print("1. 📋 General Database Analysis")
    print("   - Database structure overview")
    print("   - Table sizes and relationships")
    print("   - Fragmentation analysis")
    print("   - Overall health check")
    print()
    
    if GAME_EVENTS_ANALYZER_AVAILABLE:
        print("2. 🎮 Game Events Analysis (Detailed)")
        print("   - Event type breakdown")
        print("   - Player activity patterns")
        print("   - Time-based analysis")
        print("   - Performance recommendations")
        print()
    else:
        print("2. 🎮 Game Events Analysis (UNAVAILABLE)")
        print("   - SQLite_Game_Events.py not found")
        print()
    
    if INVENTORY_ANALYZER_AVAILABLE:
        print("3. 🎒 Item Inventory Analysis (Detailed)")
        print("   - Player inventory breakdown")
        print("   - Item distribution analysis")
        print("   - Inventory type usage")
        print("   - Player rankings by items")
        print()
    else:
        print("3. 🎒 Item Inventory Analysis (UNAVAILABLE)")
        print("   - SQLite_Item_table.py not found")
        print()
    
    available_count = sum([1, GAME_EVENTS_ANALYZER_AVAILABLE, INVENTORY_ANALYZER_AVAILABLE])
    if available_count > 1:
        print("4. 🔄 All Available Analyses (Complete Report)")
        print("5. ❌ Exit")
    else:
        print("4. ❌ Exit")
    
    print("="*70)

def get_database_path():
    """Get and validate database path from user"""
    while True:
        db_path = input("Enter the path to game.db: ").strip()
        if os.path.exists(db_path):
            return db_path
        else:
            print("❌ Error: Database file not found! Please try again.")

def get_sqlite_exe_path():
    """Get SQLite executable path (optional)"""
    sqlite_exe_path = input("Enter the path to sqlite3.exe (or press Enter to skip fragmentation analysis): ").strip()
    return sqlite_exe_path if sqlite_exe_path else None

def run_all_available_analyses(db_path: str, sqlite_exe_path: Optional[str]):
    """Run all available analyses"""
    available_analyzers = []
    
    # Always available - General analysis
    available_analyzers.append(("General Database", "general"))
    
    if GAME_EVENTS_ANALYZER_AVAILABLE:
        available_analyzers.append(("Game Events", "events"))
    
    if INVENTORY_ANALYZER_AVAILABLE:
        available_analyzers.append(("Item Inventory", "inventory"))
    
    print(f"\n🔍 Running Complete Analysis Suite...")
    print(f"Available analyzers: {len(available_analyzers)}")
    print("This may take a while for large databases...")
    
    for i, (name, analyzer_type) in enumerate(available_analyzers, 1):
        print(f"\n" + "="*60)
        print(f"PART {i}/{len(available_analyzers)}: {name.upper()} ANALYSIS")
        print("="*60)
        
        if analyzer_type == "general":
            analyzer = ConanExilesDBAnalyzer(db_path, sqlite_exe_path)
            analyzer.generate_general_report()
            
        elif analyzer_type == "events":
            events_analyzer = ConanExilesGameEventsAnalyzer(db_path)
            events_analyzer.run_analysis()
            
        elif analyzer_type == "inventory":
            inventory_analyzer = ConanExilesInventoryAnalyzer(db_path)
            inventory_analyzer.run_analysis()
    
    print(f"\n✅ Complete analysis suite finished!")
    print(f"Analyzed {len(available_analyzers)} different aspects of your database.")

def main():
    """Main function with menu system"""
    print("🏛️ Conan Exiles Database Analyzer Suite")
    print("=" * 50)
    
    # Show availability status
    available_modules = ["Core Database Analysis"]
    if GAME_EVENTS_ANALYZER_AVAILABLE:
        available_modules.append("Game Events Analysis")
    if INVENTORY_ANALYZER_AVAILABLE:
        available_modules.append("Item Inventory Analysis")
    
    print(f"Available modules: {', '.join(available_modules)}")
    
    if not GAME_EVENTS_ANALYZER_AVAILABLE:
        print("⚠️  SQLite_Game_Events.py not found - Game Events analysis unavailable")
    if not INVENTORY_ANALYZER_AVAILABLE:
        print("⚠️  SQLite_Item_table.py not found - Inventory analysis unavailable")
    
    # Get database path once
    db_path = get_database_path()
    sqlite_exe_path = get_sqlite_exe_path()
    
    print(f"\n✅ Database found: {os.path.basename(db_path)}")
    
    while True:
        show_main_menu()
        
        try:
            # Determine max choice number based on available analyzers
            available_count = sum([1, GAME_EVENTS_ANALYZER_AVAILABLE, INVENTORY_ANALYZER_AVAILABLE])
            max_choice = 5 if available_count > 1 else 4
            
            choice = input(f"\nEnter your choice (1-{max_choice}): ").strip()
            
            if choice == "1":
                print(f"\n🔍 Running General Database Analysis...")
                print("Please wait...")
                
                analyzer = ConanExilesDBAnalyzer(db_path, sqlite_exe_path)
                analyzer.generate_general_report()
                
                print(f"\n✅ General analysis complete!")
                
            elif choice == "2":
                if not GAME_EVENTS_ANALYZER_AVAILABLE:
                    print("\n❌ Game Events analysis is not available.")
                    print("Please ensure SQLite_Game_Events.py is in the same directory.")
                    continue
                    
                print(f"\n🔍 Running Game Events Analysis...")
                print("Please wait...")
                
                events_analyzer = ConanExilesGameEventsAnalyzer(db_path)
                events_analyzer.run_analysis()
                
                print(f"\n✅ Game Events analysis complete!")
                
            elif choice == "3":
                if not INVENTORY_ANALYZER_AVAILABLE:
                    print("\n❌ Inventory analysis is not available.")
                    print("Please ensure SQLite_Item_table.py is in the same directory.")
                    continue
                    
                print(f"\n🔍 Running Item Inventory Analysis...")
                print("Please wait...")
                
                inventory_analyzer = ConanExilesInventoryAnalyzer(db_path)
                inventory_analyzer.run_analysis()
                
                print(f"\n✅ Inventory analysis complete!")
                
            elif choice == "4":
                # This could be "All Analyses" or "Exit" depending on available modules
                available_count = sum([1, GAME_EVENTS_ANALYZER_AVAILABLE, INVENTORY_ANALYZER_AVAILABLE])
                
                if available_count > 1:
                    # Run all available analyses
                    run_all_available_analyses(db_path, sqlite_exe_path)
                else:
                    # Exit
                    print("\n👋 Goodbye!")
                    break
                    
            elif choice == "5" and max_choice == 5:
                print("\n👋 Goodbye!")
                break
                
            else:
                print(f"\n❌ Invalid choice. Please enter a number between 1 and {max_choice}.")
                continue
                
            # Ask if user wants to continue (except for exit)
            if choice not in ["4", "5"] or (choice == "4" and available_count > 1):
                while True:
                    continue_choice = input("\nWould you like to run another analysis? (y/n): ").strip().lower()
                    if continue_choice in ['y', 'yes']:
                        break
                    elif continue_choice in ['n', 'no']:
                        print("\n👋 Goodbye!")
                        return
                    else:
                        print("Please enter 'y' for yes or 'n' for no.")
                        
        except KeyboardInterrupt:
            print("\n\n👋 Analysis interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ An error occurred: {e}")
            print("Please try again.")

if __name__ == "__main__":
    main()
