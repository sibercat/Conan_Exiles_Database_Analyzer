import os
import sqlite3
import subprocess
from datetime import datetime, timedelta
from typing import Dict, Optional

class EventsCleanupManager:
    """Modular Events Cleanup Manager for Conan Exiles databases"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def check_sqlite3_available(self) -> bool:
        """Check if sqlite3 is available"""
        try:
            subprocess.run(['sqlite3', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except FileNotFoundError:
            print("⚠️  sqlite3 not found in PATH. Using Python sqlite3 module instead.")
            return False
    
    def run_sqlite_command(self, command: str) -> tuple:
        """Run SQLite command"""
        try:
            if self.check_sqlite3_available():
                result = subprocess.run(['sqlite3', self.db_path, command], 
                                      capture_output=True, text=True)
                return result.stdout, result.stderr
            else:
                # Fallback to Python sqlite3
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                try:
                    cursor.execute(command)
                    if command.strip().upper().startswith('SELECT'):
                        result = cursor.fetchall()
                        output = '\n'.join(['|'.join(map(str, row)) for row in result])
                    else:
                        conn.commit()
                        output = f"Rows affected: {cursor.rowcount}"
                    return output, ""
                except Exception as e:
                    return "", str(e)
                finally:
                    conn.close()
        except Exception as e:
            return None, str(e)
    
    def backup_database(self) -> bool:
        """Create database backup"""
        try:
            backup_name = f"game_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            import shutil
            shutil.copy2(self.db_path, backup_name)
            print(f"✅ Backup created: {backup_name}")
            return True
        except Exception as e:
            print(f"❌ Backup failed: {e}")
            return False
    
    def get_event_stats(self) -> Dict:
        """Get comprehensive event statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if game_events table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='game_events';")
            if not cursor.fetchone():
                return {"error": "game_events table not found"}
            
            # Get table info
            cursor.execute("PRAGMA table_info(game_events);")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Get total count
            cursor.execute("SELECT COUNT(*) FROM game_events;")
            total_events = cursor.fetchone()[0]
            
            stats = {
                'total_events': total_events,
                'columns': columns
            }
            
            # Try to find time column and get time range
            time_columns = [col for col in columns if any(word in col.lower() for word in ['time', 'date', 'stamp'])]
            
            if time_columns:
                time_col = time_columns[0]
                try:
                    if 'worldtime' in time_col.lower():
                        # Unix timestamp
                        cursor.execute(f"SELECT MIN({time_col}), MAX({time_col}) FROM game_events WHERE {time_col} IS NOT NULL;")
                        min_time, max_time = cursor.fetchone()
                        if min_time and max_time:
                            stats['oldest_date'] = datetime.fromtimestamp(min_time)
                            stats['newest_date'] = datetime.fromtimestamp(max_time)
                            stats['time_column'] = time_col
                    else:
                        # Try as datetime string
                        cursor.execute(f"SELECT MIN({time_col}), MAX({time_col}) FROM game_events WHERE {time_col} IS NOT NULL;")
                        min_time, max_time = cursor.fetchone()
                        if min_time and max_time:
                            stats['oldest_date'] = datetime.fromisoformat(min_time.replace('Z', '+00:00'))
                            stats['newest_date'] = datetime.fromisoformat(max_time.replace('Z', '+00:00'))
                            stats['time_column'] = time_col
                except:
                    pass
            
            conn.close()
            return stats
            
        except Exception as e:
            return {"error": f"Error getting stats: {e}"}
    
    def show_cleanup_recommendations(self, stats: Dict):
        """Show cleanup recommendations based on stats - FIXED VERSION"""
        print("\n🧹 EVENTS CLEANUP RECOMMENDATIONS")
        print("="*50)
        
        if 'error' in stats:
            print(f"❌ {stats['error']}")
            return
        
        print(f"Total Events: {stats['total_events']:,}")
        
        if 'oldest_date' in stats and 'newest_date' in stats:
            total_days = (stats['newest_date'] - stats['oldest_date']).days
            events_per_day = stats['total_events'] / max(total_days, 1)
            
            print(f"Date Range: {stats['oldest_date'].strftime('%Y-%m-%d')} to {stats['newest_date'].strftime('%Y-%m-%d')}")
            print(f"History Span: {total_days} days")
            print(f"Average Events/Day: {int(events_per_day):,}")
            
            print("\n💡 Recommended Cleanup Options:")
            print("────────────────────────────────")
            
            # Calculate cleanup scenarios using ACTUAL database queries
            scenarios = [
                (7, "Aggressive - Keep 1 week (minimal history)"),
                (30, "Moderate - Keep 1 month (balanced)"),
                (90, "Conservative - Keep 3 months (detailed history)")
            ]
            
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                time_col = stats['time_column']
                
                for days, description in scenarios:
                    cutoff_date = datetime.now() - timedelta(days=days)
                    if cutoff_date > stats['oldest_date']:
                        
                        # BUILD PROPER WHERE CLAUSE based on time column type
                        if 'worldtime' in time_col.lower():
                            cutoff_timestamp = int(cutoff_date.timestamp())
                            where_clause = f"{time_col} < {cutoff_timestamp}"
                        else:
                            cutoff_str = cutoff_date.isoformat()
                            where_clause = f"{time_col} < '{cutoff_str}'"
                        
                        # GET ACTUAL COUNT from database
                        cursor.execute(f"SELECT COUNT(*) FROM game_events WHERE {where_clause};")
                        events_to_delete = cursor.fetchone()[0]
                        
                        events_to_keep = stats['total_events'] - events_to_delete
                        percentage_delete = (events_to_delete / stats['total_events']) * 100
                        
                        print(f"\n{description}:")
                        print(f"  Delete: {events_to_delete:,} events ({percentage_delete:.1f}%)")
                        print(f"  Keep: {events_to_keep:,} events")
                
                conn.close()
                
            except Exception as e:
                print(f"⚠️ Could not calculate precise recommendations: {e}")
                print("Using estimated calculations instead...")
                
                # Fallback to original estimation method
                for days, description in scenarios:
                    cutoff_date = datetime.now() - timedelta(days=days)
                    if cutoff_date > stats['oldest_date']:
                        events_to_delete = int(events_per_day * (datetime.now() - cutoff_date).days)
                        events_to_keep = stats['total_events'] - events_to_delete
                        percentage_delete = (events_to_delete / stats['total_events']) * 100
                        
                        print(f"\n{description} (ESTIMATED):")
                        print(f"  Delete: ~{events_to_delete:,} events (~{percentage_delete:.1f}%)")
                        print(f"  Keep: ~{events_to_keep:,} events")
        
        # Performance recommendations (unchanged)
        if stats['total_events'] > 1000000:
            print("\n⚠️  PERFORMANCE IMPACT:")
            print("- Database has >1M events - cleanup strongly recommended")
            print("- Consider keeping 30 days or less for optimal performance")
        elif stats['total_events'] > 500000:
            print("\n⚠️  MODERATE SIZE:")
            print("- Database approaching 500K events")
            print("- Monitor performance and consider cleanup")
        else:
            print("\n✅ MANAGEABLE SIZE:")
            print("- Event count is within reasonable limits")
            print("- Cleanup optional but can improve performance")
    
    def delete_old_events(self, days_to_keep: int, dry_run: bool = True) -> bool:
        """Delete events older than specified days"""
        try:
            stats = self.get_event_stats()
            if 'error' in stats:
                print(f"❌ {stats['error']}")
                return False
            
            if 'time_column' not in stats:
                print("❌ Could not identify time column in game_events table")
                return False
            
            time_col = stats['time_column']
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            # Build appropriate WHERE clause based on time column type
            if 'worldtime' in time_col.lower():
                cutoff_timestamp = int(cutoff_date.timestamp())
                where_clause = f"{time_col} < {cutoff_timestamp}"
            else:
                cutoff_str = cutoff_date.isoformat()
                where_clause = f"{time_col} < '{cutoff_str}'"
            
            # Get count of events to delete
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM game_events WHERE {where_clause};")
            events_to_delete = cursor.fetchone()[0]
            
            if events_to_delete == 0:
                print("✅ No events found older than specified date.")
                conn.close()
                return True
            
            events_to_keep = stats['total_events'] - events_to_delete
            delete_percentage = (events_to_delete / stats['total_events']) * 100
            
            print(f"\n📊 CLEANUP SUMMARY:")
            print(f"────────────────────")
            print(f"Events to delete: {events_to_delete:,} ({delete_percentage:.1f}%)")
            print(f"Events to keep: {events_to_keep:,}")
            print(f"Cutoff date: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if dry_run:
                print(f"\n🔍 DRY RUN MODE - No changes made")
                print(f"SQL that would be executed:")
                print(f"DELETE FROM game_events WHERE {where_clause};")
                conn.close()
                return True
            
            confirm = input(f"\n⚠️  Proceed with deletion? (type 'YES' to confirm): ")
            if confirm != 'YES':
                print("Operation cancelled.")
                conn.close()
                return False
            
            # Execute cleanup
            print("\n🔄 Executing cleanup...")
            cursor.execute(f"DELETE FROM game_events WHERE {where_clause};")
            deleted_count = cursor.rowcount
            conn.commit()
            
            print(f"✅ Deleted {deleted_count:,} events")
            
            # Optimize database
            print("🔧 Optimizing database...")
            cursor.execute("PRAGMA optimize;")
            cursor.execute("VACUUM;")
            
            # Integrity check
            cursor.execute("PRAGMA integrity_check;")
            integrity_result = cursor.fetchone()[0]
            print(f"🔍 Integrity check: {integrity_result}")
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
            return False
    
    def export_cleanup_sql(self, days_to_keep: int) -> bool:
        """Export SQL script for cleanup"""
        try:
            stats = self.get_event_stats()
            if 'error' in stats or 'time_column' not in stats:
                print("❌ Cannot generate SQL - time column not identified")
                return False
            
            time_col = stats['time_column']
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            # Build SQL based on time column type
            if 'worldtime' in time_col.lower():
                cutoff_timestamp = int(cutoff_date.timestamp())
                where_clause = f"{time_col} < {cutoff_timestamp}"
            else:
                cutoff_str = cutoff_date.isoformat()
                where_clause = f"{time_col} < '{cutoff_str}'"
            
            sql_script = f"""-- Conan Exiles Events Cleanup Script
-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
-- Keeps events from last {days_to_keep} days
-- Cutoff date: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}

-- Backup recommended before running this script!

BEGIN TRANSACTION;

-- Show stats before cleanup
SELECT 'Events before cleanup:' as info, COUNT(*) as count FROM game_events;
SELECT 'Events to be deleted:' as info, COUNT(*) as count FROM game_events WHERE {where_clause};

-- Delete old events
DELETE FROM game_events WHERE {where_clause};

-- Show stats after cleanup
SELECT 'Events after cleanup:' as info, COUNT(*) as count FROM game_events;

-- Optimize database
PRAGMA optimize;
VACUUM;

-- Integrity check
PRAGMA integrity_check;

COMMIT;
"""
            
            filename = f"cleanup_events_{days_to_keep}days_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
            with open(filename, 'w') as f:
                f.write(sql_script)
            
            print(f"✅ SQL script exported: {filename}")
            print(f"Run with: sqlite3 game.db \".read {filename}\"")
            return True
            
        except Exception as e:
            print(f"❌ Error exporting SQL: {e}")
            return False

    def run_cleanup_manager(self):
        """Run the interactive cleanup manager"""
        while True:
            print("\n" + "="*60)
            print("🗑️ EVENTS CLEANUP MANAGER")
            print("="*60)
            print("1. 📊 Show Events Statistics")
            print("2. 🧹 Clean Old Events (Interactive)")
            print("3. 📝 Generate Cleanup SQL Script")
            print("4. 💾 Backup Database")
            print("5. 🔙 Return to Main Menu")
            
            choice = input("\nEnter your choice (1-5): ").strip()
            
            if choice == "1":
                print("\n🔍 Analyzing events table...")
                stats = self.get_event_stats()
                self.show_cleanup_recommendations(stats)
                
            elif choice == "2":
                print("\n🔍 Getting events statistics...")
                stats = self.get_event_stats()
                
                if 'error' in stats:
                    print(f"❌ {stats['error']}")
                    continue
                
                self.show_cleanup_recommendations(stats)
                
                while True:
                    try:
                        days_input = input("\nEnter days of events to keep (or 'c' to cancel): ").strip()
                        if days_input.lower() == 'c':
                            break
                        
                        days = int(days_input)
                        if days < 1:
                            print("❌ Please enter a positive number of days")
                            continue
                        
                        if days > 365:
                            confirm = input("⚠️  Keeping >365 days may impact performance. Continue? (y/n): ")
                            if confirm.lower() != 'y':
                                continue
                        
                        # Dry run first
                        print(f"\n🔍 DRY RUN - Analyzing cleanup for {days} days...")
                        if self.delete_old_events(days, dry_run=True):
                            proceed = input("\nProceed with actual cleanup? (y/n): ").strip().lower()
                            if proceed == 'y':
                                # Create backup first
                                if self.backup_database():
                                    self.delete_old_events(days, dry_run=False)
                                else:
                                    print("❌ Backup failed - cleanup cancelled for safety")
                        break
                        
                    except ValueError:
                        print("❌ Please enter a valid number")
                        
            elif choice == "3":
                print("\n📝 GENERATE CLEANUP SQL SCRIPT")
                stats = self.get_event_stats()
                
                if 'error' in stats:
                    print(f"❌ {stats['error']}")
                    continue
                
                self.show_cleanup_recommendations(stats)
                
                while True:
                    try:
                        days_input = input("\nEnter days of events to keep in script (or 'c' to cancel): ").strip()
                        if days_input.lower() == 'c':
                            break
                        
                        days = int(days_input)
                        if days < 1:
                            print("❌ Please enter a positive number of days")
                            continue
                        
                        self.export_cleanup_sql(days)
                        break
                        
                    except ValueError:
                        print("❌ Please enter a valid number")
                        
            elif choice == "4":
                print("\n💾 Creating database backup...")
                self.backup_database()
                
            elif choice == "5":
                break
                
            else:
                print("❌ Invalid choice. Please enter 1-5.")

# Legacy functions for backward compatibility with original script
def check_sqlite3_exe():
    """Check if sqlite3.exe exists in current directory or PATH"""
    manager = EventsCleanupManager("")
    return manager.check_sqlite3_available()

def run_sqlite_command(db_path, command):
    """Run a SQLite command using sqlite3.exe"""
    manager = EventsCleanupManager(db_path)
    output, error = manager.run_sqlite_command(command)
    return output, error

def backup_database(db_path):
    """Create a backup of the database"""
    manager = EventsCleanupManager(db_path)
    return manager.backup_database()

def get_event_stats(db_path):
    """Get statistics about events"""
    manager = EventsCleanupManager(db_path)
    stats = manager.get_event_stats()
    if 'error' not in stats and 'oldest_date' in stats:
        return {
            'total_events': stats['total_events'],
            'oldest_date': stats['oldest_date'],
            'newest_date': stats['newest_date']
        }
    return None

def show_days_recommendation(stats):
    """Show recommendations for days to keep based on event statistics"""
    print("\nRecommended cleanup options:")
    print("-----------------------------")
    print("Conservative (90 days): Keeps detailed history, good for active servers")
    print("Moderate (30 days): Balanced approach, suitable for most servers")
    print("Aggressive (7 days): Minimal history, best for performance")
    
    # Calculate days of history available
    total_days = (stats['newest_date'] - stats['oldest_date']).days
    print(f"\nYour server has {total_days} days of event history")
    
    # Calculate events per day average
    events_per_day = stats['total_events'] / max(total_days, 1)
    print(f"Average events per day: {int(events_per_day):,}")
    
    # Size-based recommendations
    if stats['total_events'] > 1000000:
        print("\nNOTE: Your events table is quite large (>1M events)")
        print("Consider using 30 days or less to improve performance")
    elif stats['total_events'] < 100000:
        print("\nNOTE: Your events table is relatively small")
        print("You can safely keep more history if desired")

def delete_old_events(db_path, days_to_keep):
    """Delete events older than specified days"""
    try:
        cutoff_time = int((datetime.now() - timedelta(days=days_to_keep)).timestamp())
        
        # Get count of events to be deleted
        count_cmd = f"SELECT COUNT(*) FROM game_events WHERE WorldTime < {cutoff_time};"
        count_output, err = run_sqlite_command(db_path, count_cmd)
        events_to_delete = int(count_output.strip() if count_output else 0)
        
        if events_to_delete == 0:
            print("No events found older than specified date.")
            return False
        
        # Get total count
        total_output, err = run_sqlite_command(db_path, "SELECT COUNT(*) FROM game_events;")
        total_events = int(total_output.strip() if total_output else 0)
        delete_percentage = (events_to_delete / total_events) * 100
        
        print(f"\nCleanup Summary:")
        print(f"----------------")
        print(f"Events to delete: {events_to_delete:,}")
        print(f"Percentage of total: {delete_percentage:.1f}%")
        print(f"Events to keep: {total_events - events_to_delete:,}")
        
        confirm = input(f"\nProceed with deletion and optimization? (y/n): ")
        if confirm.lower() != 'y':
            print("Operation cancelled.")
            return False
        
        # Execute cleanup commands
        cleanup_cmd = f"""DELETE FROM game_events WHERE WorldTime < {cutoff_time};
PRAGMA optimize;
VACUUM;
PRAGMA integrity_check;"""
        
        print("\nRunning cleanup and optimization...")
        output, err = run_sqlite_command(db_path, cleanup_cmd)
        
        if err:
            print(f"Error during cleanup: {err}")
            return False
            
        print("Cleanup completed successfully!")
        print(f"Integrity check result: {output.strip()}")
        return True
        
    except Exception as e:
        print(f"Error during cleanup: {e}")
        return False

def export_delete_sql(days_to_keep, output_file="delete_events.sql"):
    """Export SQL script to delete old events"""
    try:
        cutoff_time = int((datetime.now() - timedelta(days=days_to_keep)).timestamp())
        sql = f"""DELETE FROM game_events WHERE WorldTime < {cutoff_time};
PRAGMA optimize;
VACUUM;
PRAGMA integrity_check;"""
        
        with open(output_file, 'w') as f:
            f.write(sql)
        print(f"\nSQL script exported to: {output_file}")
        print("You can run it with:")
        print(f"sqlite3 game.db \".read {output_file}\"")
        print("Or open it with DB Browser for SQLite")
        return True
    except Exception as e:
        print(f"Error exporting SQL: {e}")
        return False

def main():
    """Main function for standalone execution"""
    print("🏛️ Conan Exiles Events Cleanup Manager")
    print("=" * 50)
    
    # Get database path
    db_path = input("Enter path to game.db (or press Enter for current directory): ").strip()
    if not db_path:
        db_path = "game.db"
    
    if not os.path.exists(db_path):
        print("❌ Error: Database file not found!")
        return
    
    # Check for sqlite3.exe (legacy compatibility)
    check_sqlite3_exe()
    
    while True:
        print("\nOptions:")
        print("1. Show events statistics")
        print("2. Delete old events (interactive)")
        print("3. Generate SQL cleanup script")
        print("4. Backup database")
        print("5. Run advanced cleanup manager")
        print("6. Exit")
        
        choice = input("\nEnter your choice (1-6): ")
        
        if choice == '1':
            stats = get_event_stats(db_path)
            if stats:
                print("\nEvents Statistics:")
                print(f"Total events: {stats['total_events']:,}")
                print(f"Oldest event: {stats['oldest_date']} (These can be safely deleted)")
                print(f"Newest event: {stats['newest_date']} (Keep recent events)")
        
        elif choice == '2':
            stats = get_event_stats(db_path)
            if stats:
                show_days_recommendation(stats)
                while True:
                    try:
                        days = input("\nEnter number of days of events to keep (or 'c' to cancel): ")
                        if days.lower() == 'c':
                            print("Operation cancelled.")
                            break
                        days = int(days)
                        if days < 1:
                            print("Please enter a positive number of days.")
                            continue
                        if days > 365:
                            confirm = input("Warning: Keeping more than 365 days of events may impact performance. Continue? (y/n): ")
                            if confirm.lower() != 'y':
                                continue
                        if backup_database(db_path):
                            delete_old_events(db_path, days)
                        break
                    except ValueError:
                        print("Please enter a valid number of days.")
                        
        elif choice == '3':
            stats = get_event_stats(db_path)
            if stats:
                show_days_recommendation(stats)
                while True:
                    try:
                        days = input("\nEnter number of days of events to keep (or 'c' to cancel): ")
                        if days.lower() == 'c':
                            print("Operation cancelled.")
                            break
                        days = int(days)
                        if days < 1:
                            print("Please enter a positive number of days.")
                            continue
                        export_delete_sql(days)
                        break
                    except ValueError:
                        print("Please enter a valid number of days.")
        
        elif choice == '4':
            backup_database(db_path)
        
        elif choice == '5':
            # Run the new advanced cleanup manager
            manager = EventsCleanupManager(db_path)
            manager.run_cleanup_manager()
        
        elif choice == '6':
            break
        
        else:
            print("Invalid choice!")
    
    print("\n✅ Thank you for using Conan Exiles Events Cleanup Manager!")

if __name__ == "__main__":
    main()
