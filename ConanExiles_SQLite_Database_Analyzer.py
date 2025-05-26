import sqlite3
import os
import subprocess
import json
import csv
import argparse
from prettytable import PrettyTable
from typing import Tuple, List, Dict, Optional, Any
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from contextlib import contextmanager

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

try:
    from SQLite_Orphaned_Items_Analysis import OrphanedItemsAnalyzer
    ORPHANED_ANALYZER_AVAILABLE = True
except ImportError:
    ORPHANED_ANALYZER_AVAILABLE = False

# Try to import the Events Cleanup Manager
try:
    from SQLite_Events_CleanUp import EventsCleanupManager
    EVENTS_CLEANUP_AVAILABLE = True
except ImportError:
    EVENTS_CLEANUP_AVAILABLE = False

# Try to import the Building Ownership Checker
try:
    from building_ownership_checker import analyze_building_ownership
    BUILDING_ANALYZER_AVAILABLE = True
except ImportError:
    BUILDING_ANALYZER_AVAILABLE = False

class ConanExilesDBAnalyzer:
    """Enhanced core database analyzer for general structure and health analysis"""
    
    # Size thresholds in bytes
    WARNING_SIZE = 730 * 1024 * 1024  # 730MB
    CRITICAL_SIZE = 1024 * 1024 * 1024  # 1GB
    
    # Performance thresholds
    SLOW_QUERY_THRESHOLD = 100000  # rows
    
    def __init__(self, db_path: str, sqlite_exe_path: Optional[str] = None):
        self.db_path = db_path
        self.sqlite_exe_path = sqlite_exe_path

    @contextmanager
    def get_db_connection(self):
        """Context manager for database connections"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            yield conn
        except sqlite3.Error as e:
            print(f"❌ Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()

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

    def analyze_performance_issues(self) -> Dict[str, Any]:
        """Analyze potential performance issues"""
        issues = {
            'missing_indexes': [],
            'large_tables_without_indexes': [],
            'high_row_tables': [],
            'fragmentation_issues': [],
            'orphaned_data': []
        }
        
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Find tables with high row counts
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                
                for table in tables:
                    table_name = table['name']
                    
                    # Get row count
                    cursor.execute(f"SELECT COUNT(*) as cnt FROM '{table_name}';")
                    row_count = cursor.fetchone()['cnt']
                    
                    if row_count > self.SLOW_QUERY_THRESHOLD:
                        issues['high_row_tables'].append({
                            'table': table_name,
                            'rows': row_count
                        })
                    
                    # Check for indexes
                    cursor.execute(f"PRAGMA index_list('{table_name}');")
                    indexes = cursor.fetchall()
                    
                    if row_count > 10000 and len(indexes) == 0:
                        issues['large_tables_without_indexes'].append({
                            'table': table_name,
                            'rows': row_count
                        })
                
                # Check for orphaned data in item_inventory (if table exists)
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='item_inventory';")
                if cursor.fetchone():
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='characters';")
                    if cursor.fetchone():
                        cursor.execute("""
                            SELECT COUNT(*) as orphaned_count
                            FROM item_inventory i
                            WHERE NOT EXISTS (
                                SELECT 1 FROM characters c WHERE c.id = i.owner_id
                            )
                        """)
                        orphaned_result = cursor.fetchone()
                        if orphaned_result and orphaned_result['orphaned_count'] > 0:
                            issues['orphaned_data'].append({
                                'type': 'orphaned_items',
                                'count': orphaned_result['orphaned_count']
                            })
                    
        except sqlite3.Error as e:
            print(f"❌ Performance analysis error: {e}")
            
        return issues

    def generate_cleanup_recommendations(self) -> List[Dict]:
        """Generate specific cleanup SQL commands"""
        recommendations = []
        
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Check if game_events table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='game_events';")
                if cursor.fetchone():
                    # Check for timestamp columns
                    cursor.execute("PRAGMA table_info(game_events);")
                    columns = [col[1].lower() for col in cursor.fetchall()]
                    
                    timestamp_col = None
                    for col in ['timestamp', 'created_at', 'event_time', 'time']:
                        if col in columns:
                            timestamp_col = col
                            break
                    
                    if timestamp_col:
                        # Check for old game events
                        try:
                            cursor.execute(f"""
                                SELECT COUNT(*) as old_events 
                                FROM game_events 
                                WHERE julianday('now') - julianday(datetime({timestamp_col}/1000, 'unixepoch')) > 30
                            """)
                            result = cursor.fetchone()
                            if result and result['old_events'] > 10000:
                                recommendations.append({
                                    'description': f"Delete {result['old_events']} game events older than 30 days",
                                    'sql': f"DELETE FROM game_events WHERE julianday('now') - julianday(datetime({timestamp_col}/1000, 'unixepoch')) > 30;",
                                    'impact': 'high'
                                })
                        except:
                            pass
                
                # Check for orphaned items
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='item_inventory';")
                if cursor.fetchone():
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='characters';")
                    if cursor.fetchone():
                        cursor.execute("""
                            SELECT COUNT(*) as orphaned 
                            FROM item_inventory i
                            WHERE NOT EXISTS (SELECT 1 FROM characters c WHERE c.id = i.owner_id)
                        """)
                        result = cursor.fetchone()
                        if result and result['orphaned'] > 0:
                            recommendations.append({
                                'description': f"Remove {result['orphaned']} orphaned items",
                                'sql': "DELETE FROM item_inventory WHERE owner_id NOT IN (SELECT id FROM characters);",
                                'impact': 'medium'
                            })
                    
        except sqlite3.Error as e:
            print(f"❌ Cleanup recommendation error: {e}")
            
        return recommendations

    def export_analysis_report(self, analysis_data: Dict, format: str = 'json'):
        """Export analysis results to file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if format == 'json':
            filename = f"conan_db_analysis_{timestamp}.json"
            with open(filename, 'w') as f:
                json.dump(analysis_data, f, indent=2, default=str)
        elif format == 'csv':
            filename = f"conan_db_analysis_{timestamp}.csv"
            # Convert nested data to flat structure for CSV
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Category', 'Metric', 'Value'])
                for category, data in analysis_data.items():
                    if isinstance(data, dict):
                        for key, value in data.items():
                            writer.writerow([category, key, value])
                    else:
                        writer.writerow([category, 'value', data])
                        
        print(f"✅ Analysis report exported to {filename}")
        return filename

    def run_automated_cleanup(self, dry_run: bool = True):
        """Run automated cleanup with safety checks"""
        if dry_run:
            print("\n🔍 DRY RUN MODE - No changes will be made")
        else:
            print("\n⚠️  LIVE MODE - Changes will be made to database")
            confirm = input("Are you sure you want to proceed? (type 'YES' to confirm): ")
            if confirm != 'YES':
                print("Cleanup cancelled.")
                return
                
        recommendations = self.generate_cleanup_recommendations()
        
        if not recommendations:
            print("\n✅ No cleanup recommendations found - database appears clean!")
            return
        
        for rec in recommendations:
            print(f"\n📌 {rec['description']}")
            print(f"   Impact: {rec['impact']}")
            print(f"   SQL: {rec['sql']}")
            
            if not dry_run:
                try:
                    with self.get_db_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(rec['sql'])
                        affected_rows = cursor.rowcount
                        conn.commit()
                        print(f"   ✅ Executed - {affected_rows} rows affected")
                except sqlite3.Error as e:
                    print(f"   ❌ Error: {e}")
                    
        if not dry_run and recommendations:
            print("\n🔧 Running VACUUM to optimize database...")
            self.run_vacuum()

    def run_vacuum(self):
        """Run VACUUM command to optimize database"""
        try:
            with self.get_db_connection() as conn:
                conn.execute("VACUUM;")
                print("✅ VACUUM completed successfully")
        except sqlite3.Error as e:
            print(f"❌ VACUUM failed: {e}")

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
        
        # Performance analysis
        perf_issues = self.analyze_performance_issues()
        if any(perf_issues.values()):
            print("\n⚠️  PERFORMANCE ISSUES DETECTED:")
            if perf_issues['large_tables_without_indexes']:
                print("\n📊 Large tables without indexes:")
                for table in perf_issues['large_tables_without_indexes']:
                    print(f"   - {table['table']}: {table['rows']:,} rows")
            
            if perf_issues['orphaned_data']:
                print("\n🗑️  Orphaned data found:")
                for orphan in perf_issues['orphaned_data']:
                    print(f"   - {orphan['type']}: {orphan['count']:,} records")
        
        print("\n💡 General Maintenance Recommendations:")
        print("- Regular database backups before maintenance")
        print("- Monitor table growth trends")
        print("- Use specialized analyzers for detailed table analysis")
        print("- Consider VACUUM command if fragmentation is high")
        print("- Run cleanup recommendations to remove unnecessary data")
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
    
    if ORPHANED_ANALYZER_AVAILABLE:
        print("4. 🏥 Database Health & Item Ownership Analysis")
        print("   - Check if cleanup is actually needed")
        print("   - Understand normal vs problematic items") 
        print("   - Safe cleanup recommendations")
        print("   - Prevent accidental chest destruction")
        print()
    else:
        print("4. 👻 Orphaned Items Analysis (UNAVAILABLE)")
        print("   - SQLite_Orphaned_Items_Analysis.py not found")
        print()
    
    if BUILDING_ANALYZER_AVAILABLE:
        print("5. 🏗️ Building Ownership Analysis")
        print("   - Building ownership by player")
        print("   - Orphaned building detection")
        print("   - Large structure identification")
        print("   - Building piece analysis")
        print()
    else:
        print("5. 🏗️ Building Ownership Analysis (UNAVAILABLE)")
        print("   - building_ownership_checker.py not found")
        print()
    
    print("6. 🔄 All Available Analyses (Complete Report)")
    print("7. 🧹 Database Cleanup Recommendations")
    
    if EVENTS_CLEANUP_AVAILABLE:
        print("8. 🗑️ Events Cleanup Manager")
        print("   - Clean old game events by date")
        print("   - Performance-focused event management")
        print("   - Export cleanup SQL scripts")
        print()
    else:
        print("8. 🗑️ Events Cleanup Manager (UNAVAILABLE)")
        print("   - SQLite_Events_CleanUp.py not found")
        print()
    
    print("9. 🔍 Interactive Query Mode")
    print("10. 📊 Export Analysis Results")
    print("11. ❌ Exit")
    
    print("="*70)

def run_interactive_mode(db_path: str):
    """Run interactive query mode"""
    print("\n🔍 INTERACTIVE QUERY MODE")
    print("Enter SQL queries to explore the database (read-only)")
    print("Type 'exit' to return to main menu")
    print("Type 'tables' to list all tables")
    print("Type 'describe <table>' to see table structure")
    
    while True:
        query = input("\nSQL> ").strip()
        
        if query.lower() == 'exit':
            break
        elif query.lower() == 'tables':
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                
                print("\nTables in database:")
                for table in tables:
                    print(f"  - {table[0]}")
                    
                conn.close()
            except sqlite3.Error as e:
                print(f"Error: {e}")
                
        elif query.lower().startswith('describe '):
            table_name = query[9:].strip()
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute(f"PRAGMA table_info('{table_name}');")
                columns = cursor.fetchall()
                
                if columns:
                    pt = PrettyTable()
                    pt.field_names = ["Column", "Type", "Not Null", "Default", "Primary Key"]
                    for col in columns:
                        pt.add_row([col[1], col[2], col[3], col[4], col[5]])
                    print(pt)
                else:
                    print(f"Table '{table_name}' not found")
                    
                conn.close()
            except sqlite3.Error as e:
                print(f"Error: {e}")
                
        else:
            # Execute query (read-only)
            dangerous_keywords = ['delete', 'update', 'insert', 'drop', 'alter', 'create']
            if any(keyword in query.lower() for keyword in dangerous_keywords):
                print("❌ Only SELECT queries are allowed in interactive mode")
                continue
                
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query)
                
                rows = cursor.fetchmany(50)  # Limit to 50 rows for display
                if rows:
                    # Create table from results
                    pt = PrettyTable()
                    pt.field_names = list(rows[0].keys())
                    
                    for row in rows:
                        pt.add_row(list(row))
                        
                    print(pt)
                    
                    # Check if more rows exist
                    cursor.execute(query)
                    all_rows = cursor.fetchall()
                    total_rows = len(all_rows)
                    if total_rows > 50:
                        print(f"\n(Showing first 50 of {total_rows} rows)")
                else:
                    print("No results returned")
                    
                conn.close()
            except sqlite3.Error as e:
                print(f"Query error: {e}")

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
    
    if ORPHANED_ANALYZER_AVAILABLE:
        available_analyzers.append(("Orphaned Items", "orphaned"))
    
    if BUILDING_ANALYZER_AVAILABLE:
        available_analyzers.append(("Building Ownership", "buildings"))
    
    print(f"\n🔍 Running Complete Analysis Suite...")
    print(f"Available analyzers: {len(available_analyzers)}")
    print("This may take a while for large databases...")
    
    analysis_results = {}
    
    for i, (name, analyzer_type) in enumerate(available_analyzers, 1):
        print(f"\n" + "="*60)
        print(f"PART {i}/{len(available_analyzers)}: {name.upper()} ANALYSIS")
        print("="*60)
        
        if analyzer_type == "general":
            analyzer = ConanExilesDBAnalyzer(db_path, sqlite_exe_path)
            analyzer.generate_general_report()
            # Store results for export
            table_info, _ = analyzer.analyze_tables()
            analysis_results['general'] = {
                'tables': table_info,
                'file_size': analyzer.get_file_size(),
                'performance_issues': analyzer.analyze_performance_issues()
            }
            
        elif analyzer_type == "events":
            events_analyzer = ConanExilesGameEventsAnalyzer(db_path)
            events_analyzer.run_analysis()
            
        elif analyzer_type == "inventory":
            inventory_analyzer = ConanExilesInventoryAnalyzer(db_path)
            inventory_analyzer.run_analysis()
            
        elif analyzer_type == "orphaned":
            orphaned_analyzer = OrphanedItemsAnalyzer(db_path)
            orphaned_analysis = orphaned_analyzer.analyze_orphaned_items()
            orphaned_analyzer.print_analysis(orphaned_analysis)
            
        elif analyzer_type == "buildings":
            print("Running building ownership analysis...")
            analyze_building_ownership(db_path)
    
    print(f"\n✅ Complete analysis suite finished!")
    print(f"Analyzed {len(available_analyzers)} different aspects of your database.")
    
    return analysis_results

def main():
    """Main function with menu system"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Conan Exiles Database Analyzer')
    parser.add_argument('database', nargs='?', help='Path to game.db file')
    parser.add_argument('--auto', action='store_true', help='Run all analyses automatically')
    parser.add_argument('--cleanup', action='store_true', help='Run cleanup recommendations')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode for cleanup')
    parser.add_argument('--export', choices=['json', 'csv'], help='Export results to file')
    parser.add_argument('--interactive', action='store_true', help='Interactive query mode')
    parser.add_argument('--events-cleanup', type=int, metavar='DAYS', help='Clean events older than DAYS')
    args = parser.parse_args()
    
    print("🏛️ Conan Exiles Database Analyzer Suite")
    print("=" * 50)
    
    # Show availability status
    available_modules = ["Core Database Analysis"]
    if GAME_EVENTS_ANALYZER_AVAILABLE:
        available_modules.append("Game Events Analysis")
    if INVENTORY_ANALYZER_AVAILABLE:
        available_modules.append("Item Inventory Analysis")
    if ORPHANED_ANALYZER_AVAILABLE:
        available_modules.append("Orphaned Items Analysis")
    if BUILDING_ANALYZER_AVAILABLE:
        available_modules.append("Building Ownership Analysis")
    if EVENTS_CLEANUP_AVAILABLE:
        available_modules.append("Events Cleanup Manager")
    
    print(f"Available modules: {', '.join(available_modules)}")
    
    if not GAME_EVENTS_ANALYZER_AVAILABLE:
        print("⚠️  SQLite_Game_Events.py not found - Game Events analysis unavailable")
    if not INVENTORY_ANALYZER_AVAILABLE:
        print("⚠️  SQLite_Item_table.py not found - Inventory analysis unavailable")
    if not ORPHANED_ANALYZER_AVAILABLE:
        print("⚠️  SQLite_Orphaned_Items_Analysis.py not found - Orphaned Items analysis unavailable")
    if not BUILDING_ANALYZER_AVAILABLE:
        print("⚠️  building_ownership_checker.py not found - Building Ownership analysis unavailable")
    if not EVENTS_CLEANUP_AVAILABLE:
        print("⚠️  SQLite_Events_CleanUp.py not found - Events Cleanup unavailable")
    
    # Get database path
    if args.database:
        db_path = args.database
        if not os.path.exists(db_path):
            print("❌ Error: Database file not found!")
            return
    else:
        db_path = get_database_path()
    
    sqlite_exe_path = None
    
    # Handle command line options
    if args.interactive:
        run_interactive_mode(db_path)
        return
        
    if args.events_cleanup:
        if not EVENTS_CLEANUP_AVAILABLE:
            print("❌ Events cleanup functionality not available - SQLite_Events_CleanUp.py not found")
            return
        cleanup_manager = EventsCleanupManager(db_path)
        print(f"🗑️ Running events cleanup for {args.events_cleanup} days...")
        if cleanup_manager.backup_database():
            cleanup_manager.delete_old_events(args.events_cleanup, dry_run=args.dry_run)
        return
        
    if args.cleanup:
        if not sqlite_exe_path:
            sqlite_exe_path = get_sqlite_exe_path()
        analyzer = ConanExilesDBAnalyzer(db_path, sqlite_exe_path)
        analyzer.run_automated_cleanup(dry_run=args.dry_run)
        return
        
    if args.auto:
        if not sqlite_exe_path:
            sqlite_exe_path = get_sqlite_exe_path()
        results = run_all_available_analyses(db_path, sqlite_exe_path)
        if args.export:
            analyzer = ConanExilesDBAnalyzer(db_path, sqlite_exe_path)
            analyzer.export_analysis_report(results, args.export)
        return
    
    # Normal interactive mode
    sqlite_exe_path = get_sqlite_exe_path()
    
    print(f"\n✅ Database found: {os.path.basename(db_path)}")
    
    while True:
        show_main_menu()
        
        try:
            choice = input(f"\nEnter your choice (1-11): ").strip()
            
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
                if not ORPHANED_ANALYZER_AVAILABLE:
                    print("\n❌ Orphaned Items analysis is not available.")
                    print("Please ensure SQLite_Orphaned_Items_Analysis.py is in the same directory.")
                    continue
                    
                print(f"\n🔍 Running Orphaned Items & Deleted Characters Analysis...")
                print("Please wait...")
                
                from SQLite_Orphaned_Items_Analysis import OrphanedItemsAnalyzer
                analyzer = OrphanedItemsAnalyzer(db_path)
                analysis = analyzer.analyze_orphaned_items()
                cleanup_commands = analyzer.print_analysis(analysis)
                analyzer.run_main_menu(analysis, cleanup_commands)
                
                # Skip the "run another analysis" prompt since orphaned analyzer has its own menu
                print(f"\n✅ Returning to main menu...")
                continue
                
            elif choice == "5":
                # Building Ownership Analysis
                if not BUILDING_ANALYZER_AVAILABLE:
                    print("\n❌ Building Ownership analysis is not available.")
                    print("Please ensure building_ownership_checker.py is in the same directory.")
                    continue
                    
                print(f"\n🔍 Running Building Ownership Analysis...")
                print("Please wait...")
                
                # Ask if user wants to check specific character IDs
                check_specific = input("\nDo you want to check specific character IDs? (y/n): ").strip().lower()
                target_chars = None
                
                if check_specific in ['y', 'yes']:
                    char_input = input("Enter character IDs separated by spaces: ").strip()
                    if char_input:
                        try:
                            target_chars = [int(x) for x in char_input.split()]
                            print(f"Will analyze characters: {target_chars}")
                        except ValueError:
                            print("Invalid character IDs entered. Running general analysis.")
                
                analyze_building_ownership(db_path, target_chars)
                print(f"\n✅ Building ownership analysis complete!")
                
            elif choice == "6":
                # Run all available analyses
                results = run_all_available_analyses(db_path, sqlite_exe_path)
                
            elif choice == "7":
                # Database cleanup recommendations
                print(f"\n🧹 Analyzing database for cleanup opportunities...")
                analyzer = ConanExilesDBAnalyzer(db_path, sqlite_exe_path)
                
                while True:
                    cleanup_choice = input("\nDo you want to run in dry-run mode first? (y/n): ").strip().lower()
                    if cleanup_choice in ['y', 'yes']:
                        analyzer.run_automated_cleanup(dry_run=True)
                        
                        # Ask if they want to proceed with actual cleanup
                        proceed = input("\nDo you want to proceed with actual cleanup? (y/n): ").strip().lower()
                        if proceed in ['y', 'yes']:
                            analyzer.run_automated_cleanup(dry_run=False)
                        break
                    elif cleanup_choice in ['n', 'no']:
                        analyzer.run_automated_cleanup(dry_run=False)
                        break
                    else:
                        print("Please enter 'y' for yes or 'n' for no.")
                        
            elif choice == "8":
                # Events Cleanup Manager
                if not EVENTS_CLEANUP_AVAILABLE:
                    print("\n❌ Events Cleanup Manager is not available.")
                    print("Please ensure SQLite_Events_CleanUp.py is in the same directory.")
                    continue
                    
                print(f"\n🗑️ Loading Events Cleanup Manager...")
                cleanup_manager = EventsCleanupManager(db_path)
                cleanup_manager.run_cleanup_manager()
                
            elif choice == "9":
                # Interactive query mode
                run_interactive_mode(db_path)
                
            elif choice == "10":
                # Export analysis results
                print(f"\n📊 Running complete analysis for export...")
                results = run_all_available_analyses(db_path, sqlite_exe_path)
                
                while True:
                    export_format = input("\nExport format (json/csv): ").strip().lower()
                    if export_format in ['json', 'csv']:
                        analyzer = ConanExilesDBAnalyzer(db_path, sqlite_exe_path)
                        filename = analyzer.export_analysis_report(results, export_format)
                        print(f"\n✅ Analysis exported to: {filename}")
                        break
                    else:
                        print("Please enter 'json' or 'csv'.")
                
            elif choice == "11":
                print("\n👋 Goodbye!")
                break
                
            else:
                print(f"\n❌ Invalid choice. Please enter a number between 1 and 11.")
                continue
                
            # Ask if user wants to continue (except for exit and orphaned analyzer)
            if choice not in ["11", "4"]:  # Don't ask for orphaned analyzer since it has its own menu
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
