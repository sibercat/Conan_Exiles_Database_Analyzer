import sqlite3
import os
from prettytable import PrettyTable
from typing import Dict, Optional

class ConanExilesGameEventsAnalyzer:
    """Specialized analyzer for Conan Exiles game_events table"""
    
    # Common Conan Exiles Event Type mappings
    EVENT_TYPE_MAPPING = {
        # Player Events
        1: "Player Login",
        2: "Player Logout", 
        3: "Player Death",
        4: "Player Respawn",
        5: "Player Level Up",
        86: "Player Movement/Position Update",
        87: "Player Stats Update",
        88: "Player Inventory Change",
        89: "Player Equipment Change",
        90: "Player Chat Message",
        91: "Player Command",
        92: "Player Action/Interaction",
        93: "Player Crafting",
        94: "Player Building",
        95: "Player Harvesting",
        
        # Combat Events  
        99: "Combat Damage Dealt",
        100: "Combat Damage Received",
        101: "Combat Kill",
        102: "Combat PvP",
        103: "Combat NPC Kill",
        104: "Weapon/Tool Usage",
        105: "Combat Block/Dodge",
        106: "Combat Status Effect",
        
        # Building/Construction
        170: "Building Placed",
        171: "Building Destroyed", 
        172: "Building Damaged",
        173: "Building Repaired",
        174: "Building Decay",
        175: "Building Permission Change",
        176: "Door/Gate Usage",
        177: "Container Access",
        178: "Workstation Usage",
        
        # Server/Admin Events
        200: "Server Start",
        201: "Server Stop", 
        202: "Admin Command",
        203: "Ban/Kick Event",
        204: "Wipe Event",
        
        # Clan Events
        220: "Clan Created",
        221: "Clan Disbanded",
        222: "Clan Member Join",
        223: "Clan Member Leave",
        224: "Clan Rank Change",
        
        # Economy/Trading (if mods)
        250: "Trade Transaction",
        251: "Shop Purchase",
        252: "Currency Change",
        
        # Other Common Events
        300: "NPC Spawn",
        301: "NPC Death",
        302: "Resource Spawn",
        303: "Weather Change",
        304: "Time/Day Cycle",
        305: "Server Performance Log"
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

    def get_event_type_name(self, event_id: int) -> str:
        """Get human-readable name for event type ID"""
        if event_id in self.EVENT_TYPE_MAPPING:
            return f"{self.EVENT_TYPE_MAPPING[event_id]} ({event_id})"
        else:
            return f"Unknown Event Type {event_id}"

    def analyze_event_patterns(self) -> Dict:
        """Analyze patterns in game events for additional insights"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if game_events table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='game_events';")
            if not cursor.fetchone():
                return {"error": "game_events table not found"}
            
            cursor.execute("PRAGMA table_info(game_events);")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            patterns = {}
            
            # Look for player-related patterns
            player_columns = [col for col in column_names if 'player' in col.lower() or 'user' in col.lower()]
            if player_columns:
                player_col = player_columns[0]
                cursor.execute(f"SELECT {player_col}, COUNT(*) FROM game_events WHERE {player_col} IS NOT NULL GROUP BY {player_col} ORDER BY COUNT(*) DESC LIMIT 10;")
                patterns["top_players_by_events"] = cursor.fetchall()
            
            # Look for time patterns (if timestamp exists)
            time_columns = [col for col in column_names if any(word in col.lower() for word in ['time', 'date', 'stamp'])]
            if time_columns:
                time_col = time_columns[0]
                try:
                    # Try to get hourly distribution
                    cursor.execute(f"""
                        SELECT strftime('%H', {time_col}) as hour, COUNT(*) 
                        FROM game_events 
                        WHERE {time_col} IS NOT NULL 
                        GROUP BY hour 
                        ORDER BY hour
                    """)
                    patterns["hourly_distribution"] = cursor.fetchall()
                    
                    # Try to get daily distribution
                    cursor.execute(f"""
                        SELECT date({time_col}) as event_date, COUNT(*) 
                        FROM game_events 
                        WHERE {time_col} IS NOT NULL 
                        GROUP BY event_date 
                        ORDER BY event_date DESC 
                        LIMIT 30
                    """)
                    patterns["daily_distribution"] = cursor.fetchall()
                except:
                    pass
            
            conn.close()
            return patterns
            
        except Exception as e:
            return {"error": f"Error analyzing patterns: {e}"}

    def analyze_game_events_table(self) -> Dict:
        """Analyze the game_events table in detail"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if game_events table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='game_events';")
            if not cursor.fetchone():
                return {"error": "game_events table not found"}
            
            # Get table structure
            cursor.execute("PRAGMA table_info(game_events);")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            print(f"📋 Game Events Table Columns: {', '.join(column_names)}")
            
            # Get total count
            cursor.execute("SELECT COUNT(*) FROM game_events;")
            total_events = cursor.fetchone()[0]
            
            analysis = {
                "total_events": total_events,
                "columns": column_names,
                "event_type_analysis": {},
                "recent_events": [],
                "oldest_events": [],
                "size_impact": {}
            }
            
            # Analyze event types (assuming there's an event_type or similar column)
            event_type_columns = [col for col in column_names if 'type' in col.lower() or 'event' in col.lower()]
            
            if event_type_columns:
                main_type_col = event_type_columns[0]  # Use first matching column
                cursor.execute(f"SELECT {main_type_col}, COUNT(*) as count FROM game_events GROUP BY {main_type_col} ORDER BY count DESC LIMIT 20;")
                event_types = cursor.fetchall()
                analysis["event_type_analysis"] = {
                    "column_used": main_type_col,
                    "top_events": event_types
                }
            
            # Get recent events (if there's a timestamp column)
            timestamp_columns = [col for col in column_names if any(word in col.lower() for word in ['time', 'date', 'stamp', 'created'])]
            
            if timestamp_columns:
                timestamp_col = timestamp_columns[0]
                try:
                    cursor.execute(f"SELECT * FROM game_events ORDER BY {timestamp_col} DESC LIMIT 10;")
                    analysis["recent_events"] = cursor.fetchall()
                    
                    cursor.execute(f"SELECT * FROM game_events ORDER BY {timestamp_col} ASC LIMIT 5;")
                    analysis["oldest_events"] = cursor.fetchall()
                except:
                    pass  # Handle cases where timestamp column might not be sortable
            
            # Estimate size contribution
            cursor.execute("SELECT * FROM game_events LIMIT 100;")
            sample_rows = cursor.fetchall()
            if sample_rows:
                avg_row_size = sum(len(str(row)) for row in sample_rows) / len(sample_rows)
                estimated_table_size = avg_row_size * total_events
                analysis["size_impact"] = {
                    "estimated_size_bytes": estimated_table_size,
                    "avg_row_size": avg_row_size
                }
            
            conn.close()
            return analysis
            
        except sqlite3.Error as e:
            return {"error": f"SQLite error: {e}"}
        except Exception as e:
            return {"error": f"Error: {e}"}

    def print_game_events_analysis(self, analysis: Dict) -> None:
        """Print detailed analysis of game_events table"""
        if "error" in analysis:
            print(f"\n❌ Game Events Analysis Error: {analysis['error']}")
            return
        
        print("\n" + "="*80)
        print("🎮 CONAN EXILES GAME EVENTS ANALYSIS")
        print("="*80)
        
        print(f"\n📊 Overview:")
        print(f"Total Events: {analysis['total_events']:,}")
        print(f"Table Columns: {', '.join(analysis['columns'])}")
        
        if analysis.get('size_impact'):
            size_info = analysis['size_impact']
            print(f"Estimated Table Size: {self.format_size(size_info['estimated_size_bytes'])}")
            print(f"Average Row Size: {size_info['avg_row_size']:.1f} bytes")
        
        # Event type analysis
        if analysis.get('event_type_analysis') and analysis['event_type_analysis'].get('top_events'):
            print(f"\n🔥 Top Event Types (by frequency):")
            print(f"Analysis based on column: '{analysis['event_type_analysis']['column_used']}'")
            
            event_table = PrettyTable()
            event_table.field_names = ["Event Type", "ID", "Count", "Percentage", "Est. Size Impact"]
            event_table.align["Event Type"] = "l"
            event_table.align["ID"] = "r"
            event_table.align["Count"] = "r"
            event_table.align["Percentage"] = "r"
            event_table.align["Est. Size Impact"] = "r"
            
            total_events = analysis['total_events']
            avg_row_size = analysis.get('size_impact', {}).get('avg_row_size', 100)
            
            for event_type, count in analysis['event_type_analysis']['top_events']:
                percentage = (count / total_events) * 100
                size_impact = count * avg_row_size
                event_name = self.get_event_type_name(int(event_type)) if str(event_type).isdigit() else str(event_type)
                
                # Split event name and ID for better display
                if "(" in event_name and event_name.endswith(")"):
                    name_part = event_name.split(" (")[0]
                    id_part = event_name.split(" (")[1].rstrip(")")
                else:
                    name_part = event_name
                    id_part = str(event_type)
                
                event_table.add_row([
                    name_part[:35],  # Truncate long event names
                    id_part,
                    f"{count:,}",
                    f"{percentage:.1f}%",
                    self.format_size(size_impact)
                ])
            
            print(event_table)
        
        # Recent events sample
        if analysis.get('recent_events'):
            print(f"\n🕐 Recent Events Sample (Latest 10):")
            recent_table = PrettyTable()
            if analysis['recent_events']:
                # Use column names for header
                recent_table.field_names = [col[:15] for col in analysis['columns']]  # Truncate column names
                for row in analysis['recent_events'][:5]:  # Show only first 5 for readability
                    truncated_row = [str(field)[:15] if field is not None else "NULL" for field in row]
                    recent_table.add_row(truncated_row)
                print(recent_table)
        
        # Advanced pattern analysis
        patterns = self.analyze_event_patterns()
        if patterns and not patterns.get("error"):
            if patterns.get("top_players_by_events"):
                print(f"\n👥 Most Active Players (by event count):")
                player_table = PrettyTable()
                player_table.field_names = ["Player", "Event Count"]
                player_table.align["Player"] = "l"
                player_table.align["Event Count"] = "r"
                
                for player, count in patterns["top_players_by_events"][:10]:
                    player_table.add_row([str(player)[:25], f"{count:,}"])
                print(player_table)
            
            if patterns.get("hourly_distribution"):
                print(f"\n🕐 Event Distribution by Hour:")
                hour_table = PrettyTable()
                hour_table.field_names = ["Hour", "Event Count", "Activity Level"]
                hour_table.align["Hour"] = "r"
                hour_table.align["Event Count"] = "r"
                hour_table.align["Activity Level"] = "l"
                
                max_hourly = max(count for _, count in patterns["hourly_distribution"]) if patterns["hourly_distribution"] else 0
                for hour, count in patterns["hourly_distribution"]:
                    activity_level = "█" * int((count / max_hourly) * 10) if max_hourly > 0 else ""
                    hour_table.add_row([f"{hour}:00", f"{count:,}", activity_level])
                print(hour_table)
            
            if patterns.get("daily_distribution"):
                print(f"\n📅 Daily Event Distribution (Last 30 days):")
                daily_table = PrettyTable()
                daily_table.field_names = ["Date", "Event Count", "Activity Level"]
                daily_table.align["Date"] = "l"
                daily_table.align["Event Count"] = "r"
                daily_table.align["Activity Level"] = "l"
                
                max_daily = max(count for _, count in patterns["daily_distribution"]) if patterns["daily_distribution"] else 0
                for date, count in patterns["daily_distribution"][:10]:  # Show only first 10 days
                    activity_level = "█" * int((count / max_daily) * 20) if max_daily > 0 else ""
                    daily_table.add_row([str(date), f"{count:,}", activity_level[:20]])
                print(daily_table)
        
        # Enhanced Recommendations
        print(f"\n💡 Game Events Recommendations:")
        print("="*50)
        
        if analysis['total_events'] > 100000:
            print("⚠️  High event count detected - consider regular cleanup")
        if analysis['total_events'] > 1000000:
            print("🚨 Very high event count - implement automated cleanup")
        
        if analysis.get('event_type_analysis') and analysis['event_type_analysis'].get('top_events'):
            top_event = analysis['event_type_analysis']['top_events'][0]
            top_event_type, top_count = top_event
            event_name = self.get_event_type_name(int(top_event_type)) if str(top_event_type).isdigit() else str(top_event_type)
            
            if top_count > analysis['total_events'] * 0.3:  # If one event type is >30% of all events
                print(f"🎯 '{event_name}' dominates with {top_count:,} events ({(top_count/analysis['total_events']*100):.1f}%)")
                
                # Specific recommendations based on event type
                event_id = int(top_event_type) if str(top_event_type).isdigit() else 0
                if event_id == 86:  # Player Movement
                    print("  💡 Consider reducing player position update frequency in server settings")
                elif event_id == 92:  # Player Actions
                    print("  💡 High player interaction - normal for active server")
                elif event_id == 177:  # Container Access
                    print("  💡 Frequent container access - consider if all need logging")
                elif event_id == 174:  # Building Decay
                    print("  💡 Building decay events - consider cleanup of old structures")
                elif event_id == 99 or event_id == 100:  # Combat
                    print("  💡 High combat activity - normal for PvP servers")
        
        print("\n🔧 Maintenance Suggestions:")
        print("- Consider archiving events older than 30-90 days")
        print("- Use VACUUM command after cleanup to reclaim space")
        print("- Monitor top event types for unusual spikes")
        print("- Set up automated cleanup for high-frequency events")
        
        if analysis.get('size_impact'):
            size_mb = analysis['size_impact']['estimated_size_bytes'] / (1024 * 1024)
            if size_mb > 100:
                print(f"- Large events table ({size_mb:.0f}MB) - prioritize cleanup")

    def run_analysis(self) -> None:
        """Run the complete game events analysis"""
        print("🔍 Analyzing game_events table...")
        
        # Focus on game events analysis
        events_analysis = self.analyze_game_events_table()
        self.print_game_events_analysis(events_analysis)
        
        # Basic database info
        try:
            actual_file_size = os.path.getsize(self.db_path)
            print(f"\n📏 Database File Size: {self.format_size(actual_file_size)}")
        except:
            print("\n📏 Could not determine database file size")

def main():
    """Main function for standalone execution"""
    print("🏛️ Conan Exiles Database Analyzer - Game Events Focus")
    print("=" * 60)
    
    db_path = input("Enter the path to game.db: ").strip()
    
    if not os.path.exists(db_path):
        print("❌ Error: Database file not found!")
        return
    
    print(f"\n🔍 Analyzing database: {os.path.basename(db_path)}")
    print("Focusing on game_events analysis...")
    print("Please wait...")
    
    analyzer = ConanExilesGameEventsAnalyzer(db_path)
    analyzer.run_analysis()
    
    print(f"\n✅ Game events analysis complete!")

if __name__ == "__main__":
    main()