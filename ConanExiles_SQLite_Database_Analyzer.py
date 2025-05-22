import sqlite3
import os
import subprocess
from prettytable import PrettyTable
from typing import Tuple, List, Dict, Optional
from collections import Counter
from datetime import datetime

class ConanExilesDBAnalyzer:
    # Size thresholds in bytes
    WARNING_SIZE = 730 * 1024 * 1024  # 730MB
    CRITICAL_SIZE = 1024 * 1024 * 1024  # 1GB
    
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
                except:
                    pass
            
            conn.close()
            return patterns
            
        except Exception as e:
            return {"error": f"Error analyzing patterns: {e}"}
        """Get database fragmentation information"""
        if not self.sqlite_exe_path:
            return {'freelist_count': 0, 'page_count': 0, 'page_size': 0}
            
        return {
            'freelist_count': int(self.run_sqlite_command("PRAGMA freelist_count;") or 0),
            'page_count': int(self.run_sqlite_command("PRAGMA page_count;") or 0),
            'page_size': int(self.run_sqlite_command("PRAGMA page_size;") or 0)
        }

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
                
                max_hourly = max(count for _, count in patterns["hourly_distribution"])
                for hour, count in patterns["hourly_distribution"]:
                    activity_level = "█" * int((count / max_hourly) * 10) if max_hourly > 0 else ""
                    hour_table.add_row([f"{hour}:00", f"{count:,}", activity_level])
                print(hour_table)
        
        # Enhanced Recommendations
        print(f"\n💡 Specific Recommendations:")
        if analysis['total_events'] > 100000:
            print("- ⚠️  High event count detected - consider regular cleanup")
        if analysis['total_events'] > 1000000:
            print("- 🚨 Very high event count - implement automated cleanup")
        
        if analysis.get('event_type_analysis') and analysis['event_type_analysis'].get('top_events'):
            top_event = analysis['event_type_analysis']['top_events'][0]
            top_event_type, top_count = top_event
            event_name = self.get_event_type_name(int(top_event_type)) if str(top_event_type).isdigit() else str(top_event_type)
            
            if top_count > analysis['total_events'] * 0.3:  # If one event type is >30% of all events
                print(f"- 🎯 '{event_name}' dominates with {top_count:,} events ({(top_count/analysis['total_events']*100):.1f}%)")
                
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
        
        print("- 📅 Consider archiving events older than 30-90 days")
        print("- 🔧 Use VACUUM command after cleanup to reclaim space")
        print("- 📊 Monitor top event types for unusual spikes")

    def generate_report(self, focus_on_events: bool = True) -> None:
        """Generate and print analysis report"""
        table_info, sqlite_size = self.analyze_tables()
        actual_file_size = self.get_file_size()
        frag_info = self.get_fragmentation_info() if self.sqlite_exe_path else None
        
        if not table_info:
            print("No tables found or error occurred!")
            return
        
        # Game events analysis first if requested
        if focus_on_events:
            events_analysis = self.analyze_game_events_table()
            self.print_game_events_analysis(events_analysis)
        
        # Standard table analysis
        print("\n" + "="*80)
        print("📋 GENERAL DATABASE ANALYSIS")
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
        
        print("\nNote: Overhead includes indexes, free space, SQLite page structures, and other metadata")

def main():
    print("🏛️ Conan Exiles Database Analyzer")
    print("=" * 50)
    
    sqlite_exe_path = input("Enter the path to sqlite3.exe (or press Enter to skip fragmentation analysis): ").strip()
    db_path = input("Enter the path to game.db: ").strip()
    
    if not os.path.exists(db_path):
        print("❌ Error: Database file not found!")
        return
    
    focus_events = input("Focus on game_events analysis? (y/n, default: y): ").strip().lower()
    focus_events = focus_events != 'n'
    
    print(f"\n🔍 Analyzing database: {os.path.basename(db_path)}")
    print("Please wait...")
    
    analyzer = ConanExilesDBAnalyzer(db_path, sqlite_exe_path if sqlite_exe_path else None)
    analyzer.generate_report(focus_on_events=focus_events)
    
    print(f"\n✅ Analysis complete!")

if __name__ == "__main__":
    main()