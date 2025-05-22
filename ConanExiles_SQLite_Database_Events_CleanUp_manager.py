import os
from datetime import datetime, timedelta
import subprocess

def check_sqlite3_exe():
    """Check if sqlite3.exe exists in current directory or PATH"""
    try:
        subprocess.run(['sqlite3', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        print("Error: sqlite3.exe not found! Please ensure it's in the current directory or PATH")
        return False

def run_sqlite_command(db_path, command):
    """Run a SQLite command using sqlite3.exe"""
    try:
        result = subprocess.run(['sqlite3', db_path, command], 
                              capture_output=True, 
                              text=True)
        return result.stdout, result.stderr
    except Exception as e:
        return None, str(e)

def backup_database(db_path):
    """Create a backup of the database"""
    try:
        backup_name = f"game_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        os.system(f"copy \"{db_path}\" \"{backup_name}\"")
        print(f"Backup created: {backup_name}")
        return True
    except Exception as e:
        print(f"Backup failed: {e}")
        return False

def get_event_stats(db_path):
    """Get statistics about events"""
    try:
        # Get total count
        count_output, err = run_sqlite_command(db_path, "SELECT COUNT(*) FROM game_events;")
        total_events = int(count_output.strip() if count_output else 0)
        
        # Get time range
        time_output, err = run_sqlite_command(db_path, 
            "SELECT MIN(WorldTime), MAX(WorldTime) FROM game_events;")
        min_time, max_time = map(int, time_output.strip().split('|'))
        
        oldest_date = datetime.fromtimestamp(min_time)
        newest_date = datetime.fromtimestamp(max_time)
        
        return {
            'total_events': total_events,
            'oldest_date': oldest_date,
            'newest_date': newest_date
        }
    except Exception as e:
        print(f"Error getting stats: {e}")
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
    print("Conan Exiles Events Manager")
    print("==========================")
    
    # Check for sqlite3.exe
    if not check_sqlite3_exe():
        return
    
    # Get database path
    db_path = input("Enter path to game.db (or press Enter for current directory): ").strip()
    if not db_path:
        db_path = "game.db"
    
    if not os.path.exists(db_path):
        print("Error: Database file not found!")
        return
    
    while True:
        print("\nOptions:")
        print("1. Show events statistics")
        print("2. Delete old events (interactive)")
        print("3. Generate SQL cleanup script")
        print("4. Backup database")
        print("5. Exit")
        
        choice = input("\nEnter your choice (1-5): ")
        
        if choice == '1':
            stats = get_event_stats(db_path)
            if stats:
                print("\nEvents Statistics:")
                print(f"Total events: {stats['total_events']:,}")
                print(f"Oldest event: {stats['oldest_date']} (These can be safely deleted)")
                print(f"Newest event: {stats['newest_date']} (Keep recent events)")
        
        elif choice == '2':
            stats = get_event_stats(db_path)
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
            break
        
        else:
            print("Invalid choice!")
    
    print("\nThank you for using Conan Exiles Events Manager!")

if __name__ == "__main__":
    main()