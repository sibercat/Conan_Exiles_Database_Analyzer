# 🏛️ Conan Exiles Database Analyzer Suite

A comprehensive Python toolkit for analyzing Conan Exiles `game.db` SQLite databases. This suite provides detailed insights into your server's database structure, player inventories, game events, orphaned data, and performance optimization opportunities.

## 🚀 Features

### 📋 General Database Analysis
- **Database Structure Overview**: Complete table analysis with row counts, columns, and indexes
- **Size Analysis**: Detailed breakdown of database storage usage and overhead
- **Fragmentation Detection**: Identifies database fragmentation and recommends maintenance
- **Health Monitoring**: Size warnings and performance recommendations
- **SQLite Optimization**: VACUUM recommendations and maintenance suggestions

### 🎮 Game Events Analysis
- **Event Type Breakdown**: Analysis of all game events with human-readable names
- **Player Activity Patterns**: Most active players and behavioral insights
- **Time-based Analysis**: Hourly and daily activity distribution with visual charts
- **Performance Impact**: Event frequency analysis and cleanup recommendations
- **Specialized Recommendations**: Event-type specific maintenance suggestions

### 🎒 Item Inventory Analysis
- **Player Rankings**: Top players by item count with detailed breakdowns
- **Inventory Distribution**: Analysis of player vs container storage usage
- **Item Popularity**: Most common items and their distribution across players
- **Storage Optimization**: Inventory type usage patterns and recommendations
- **Player Name Resolution**: Links owner IDs to actual character names

### 👻 Orphaned Items & Deleted Characters Analysis
- **Deleted Character Detection**: Identifies orphaned items from deleted characters
- **Character ID Patterns**: Analyzes deletion patterns (mass cleanup vs individual departures)
- **Item Recovery Insights**: Shows what items belonged to deleted characters
- **Database Cleanup**: Provides SQL commands to remove orphaned data
- **Deletion Statistics**: Differentiates between character IDs and actual players

### 🧹 Database Cleanup & Maintenance
- **Automated Cleanup Recommendations**: Identifies unnecessary data for removal
- **Dry Run Mode**: Preview cleanup operations before execution
- **SQL Command Generation**: Provides safe cleanup commands with explanations
- **VACUUM Operations**: Database optimization and space reclamation
- **Safety Checks**: Multiple confirmations before any destructive operations

### 🔍 Interactive Query Mode
- **SQL Console**: Execute read-only queries directly on the database
- **Table Explorer**: List all tables and examine their structure
- **Data Investigation**: Explore your database interactively
- **Safety Restrictions**: Prevents destructive operations in interactive mode

## 📁 File Structure

```
Conan-Exiles-Database-Analyzer/
├── ConanExiles_SQLite_Database_Analyzer.py  # Main controller with menu system
├── SQLite_Game_Events.py                    # Game events specialist analyzer
├── SQLite_Item_table.py                     # Item inventory specialist analyzer
├── SQLite_Orphaned_Items_Analysis.py        # Orphaned data specialist analyzer
├── !Start.cmd                               # Windows batch file for easy launching
└── README.md                                # This file
```

## 🛠️ Installation

### Prerequisites
- Python 3.6 or higher
- Required Python packages:
  ```bash
  pip install prettytable
  ```

### Setup
1. Clone or download this repository
2. Ensure all Python files are in the same directory
3. Install required dependencies
4. Locate your Conan Exiles `game.db` file (usually in server save directory)

## 🎯 Usage

### Quick Start
```bash
python ConanExiles_SQLite_Database_Analyzer.py
```

Or on Windows:
```bash
# Double click !Start.cmd
```

### Command Line Options
```bash
# Run all analyses automatically
python ConanExiles_SQLite_Database_Analyzer.py --auto

# Run cleanup recommendations
python ConanExiles_SQLite_Database_Analyzer.py --cleanup --dry-run

# Interactive query mode
python ConanExiles_SQLite_Database_Analyzer.py --interactive

# Export results to JSON
python ConanExiles_SQLite_Database_Analyzer.py --auto --export json
```

### Menu Options
The analyzer provides an interactive menu system:

1. **📋 General Database Analysis** - Complete database health check
2. **🎮 Game Events Analysis** - Detailed event logging analysis  
3. **🎒 Item Inventory Analysis** - Player inventory deep dive
4. **👻 Orphaned Items & Deleted Characters Analysis** - Find deleted character data
5. **🔄 All Available Analyses** - Run complete analysis suite
6. **🧹 Database Cleanup Recommendations** - Automated maintenance suggestions
7. **🔍 Interactive Query Mode** - SQL console for database exploration
8. **📊 Export Analysis Results** - Save results to JSON or CSV
9. **❌ Exit**

### Example Output

#### Player Inventory Rankings
```
👥 TOP PLAYERS BY ITEM COUNT:
┌──────┬─────────────────────┬─────────────────────┬────────────┬─────────────────────────────┬────────────┬──────────────────┐
│ Rank │ Player ID           │ Player Name         │ Item Count │ Inventory Types             │ Percentage │ Est. Size Impact │
├──────┼─────────────────────┼─────────────────────┼────────────┼─────────────────────────────┼────────────┼──────────────────┤
│  1   │ sibercat-7415       │ SiberCat            │ 2,847      │ Player Inventory, Large     │ 12.35%     │ 284.7 KB        │
│      │                     │                     │            │ Chest, Vault (+3 more)     │            │                  │
└──────┴─────────────────────┴─────────────────────┴────────────┴─────────────────────────────┴────────────┴──────────────────┘
```

#### Orphaned Items Analysis
```
📊 Summary:
Existing Characters: 324
Deleted Character IDs: 6,520 (includes respawns, resets, etc.)
Total Orphaned Items: 142,271
Character ID Turnover: 95.3% of all character IDs ever created
💡 Note: Deleted Character IDs ≠ Unique Players Lost
   Many IDs come from character respawns, resets, and server maintenance
```

#### Game Events Analysis
```
🔥 Top Event Types (by frequency):
┌─────────────────────────────────────┬─────┬─────────┬────────────┬──────────────────┐
│ Event Type                          │ ID  │ Count   │ Percentage │ Est. Size Impact │
├─────────────────────────────────────┼─────┼─────────┼────────────┼──────────────────┤
│ Player Movement/Position Update     │ 86  │ 145,023 │ 34.2%      │ 14.5 MB         │
│ Container Access                    │ 177 │ 89,156  │ 21.1%      │ 8.9 MB          │
│ Player Action/Interaction           │ 92  │ 67,234  │ 15.9%      │ 6.7 MB          │
└─────────────────────────────────────┴─────┴─────────┴────────────┴──────────────────┘
```

## 🔧 Advanced Features

### SQLite3.exe Integration
For enhanced fragmentation analysis, provide the path to `sqlite3.exe`:
- Download from [SQLite.org](https://sqlite.org/download.html)
- Enables advanced PRAGMA commands for detailed database health metrics

### Modular Design
Each analyzer can be run independently:
```bash
# Run only inventory analysis
python SQLite_Item_table.py

# Run only game events analysis  
python SQLite_Game_Events.py

# Run only orphaned items analysis
python SQLite_Orphaned_Items_Analysis.py
```

### Export Capabilities
- **JSON Export**: Structured data for further processing
- **CSV Export**: Spreadsheet-compatible format
- **Deleted Character Lists**: Export lists of deleted characters for investigation

### Size Warnings
The analyzer provides automatic warnings for:
- **730MB+**: Size warning with maintenance recommendations
- **1GB+**: Critical size warning with immediate action items

## 📊 Database Insights

### What You'll Learn
- **Storage Optimization**: Which tables consume the most space
- **Player Behavior**: Activity patterns and inventory usage
- **Performance Issues**: High-frequency events causing bloat
- **Maintenance Needs**: Fragmentation and cleanup opportunities
- **Server Health**: Overall database condition and recommendations
- **Character Lifecycle**: Understanding character creation/deletion patterns
- **Data Recovery**: Identifying recoverable character information

### Common Findings
- **Event Log Bloat**: Player movement events often dominate storage
- **Inventory Hoarding**: Identifying players with excessive items
- **Inactive Data**: Old player data consuming unnecessary space
- **Fragmentation**: Database efficiency degradation over time
- **Orphaned Items**: Items from deleted characters taking up space
- **Character Turnover**: Distinguishing between real player departures and technical deletions

## 🛡️ Safety Features

- **Read-Only Analysis**: Never modifies your database during analysis
- **Dry Run Mode**: Preview all cleanup operations before execution
- **Multiple Confirmations**: Requires explicit confirmation for destructive operations
- **Error Handling**: Graceful handling of corrupted or locked databases
- **Backup Reminders**: Automatic recommendations for database backups
- **SQL Validation**: Prevents dangerous queries in interactive mode

## 📋 Requirements

### System Requirements
- **Operating System**: Windows, Linux, or macOS
- **Python Version**: 3.6+
- **Memory**: 512MB+ RAM (more for large databases)
- **Storage**: Minimal - analyzer is lightweight

### Database Compatibility
- **Conan Exiles**: All server versions
- **File Format**: SQLite 3.x databases
- **Size Limits**: Tested with databases up to 5GB
- **Game Modes**: Works with all game modes (PvE, PvP, PvE-C)

## 🔍 Troubleshooting

### Common Issues

**"Database file not found"**
- Ensure the path to `game.db` is correct
- Check file permissions
- Verify the database isn't currently locked by the game server

**"Missing module" warnings**
- Ensure all `.py` files are in the same directory
- Check that file names match exactly
- Verify Python can import the modules

**High "Deleted Characters" count**
- This is normal! The number represents character IDs, not unique players
- Includes character respawns, resets, and server maintenance operations
- Use the orphaned items analysis to understand the real impact

**Performance Issues**
- Large databases (1GB+) may take several minutes to analyze
- Close other applications to free up memory
- Consider running analysis during low server activity

### Getting Help
If you encounter issues:
1. Check that your `game.db` file isn't corrupted
2. Ensure you have the latest version of Python
3. Verify all required dependencies are installed
4. Make sure the game server isn't currently using the database

## 🤝 Contributing

Contributions are welcome! Areas for improvement:
- Additional game event type mappings
- Enhanced visualization features
- Support for additional database tables
- Performance optimizations for large databases
- Additional export formats
- Character name recovery algorithms
- Advanced cleanup strategies

## 📜 License

This project is open source. Feel free to modify and distribute according to your needs.

## ⚠️ Disclaimer

This tool is for analysis purposes only. Always backup your database before performing any maintenance operations. While the analyzer includes cleanup recommendations, you should always verify these are appropriate for your server before execution.

---

**Happy analyzing! 🎮**
