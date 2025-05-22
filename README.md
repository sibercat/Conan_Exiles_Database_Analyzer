# 🏛️ Conan Exiles Database Analyzer Suite

A comprehensive Python toolkit for analyzing Conan Exiles `game.db` SQLite databases. This suite provides detailed insights into your server's database structure, player inventories, game events, and performance optimization opportunities.

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

## 📁 File Structure

```
Conan-Exiles-Database-Analyzer/
├── ConanExiles_SQLite_Database_Analyzer.py  # Main controller with menu system
├── SQLite_Game_Events.py                    # Game events specialist analyzer
├── SQLite_Item_table.py                     # Item inventory specialist analyzer
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
Or

```Double click !Start.cmd```

### Menu Options
The analyzer provides an interactive menu system:

1. **📋 General Database Analysis** - Complete database health check
2. **🎮 Game Events Analysis** - Detailed event logging analysis  
3. **🎒 Item Inventory Analysis** - Player inventory deep dive
4. **🔄 All Available Analyses** - Run complete analysis suite
5. **❌ Exit**

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
```

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

### Common Findings
- **Event Log Bloat**: Player movement events often dominate storage
- **Inventory Hoarding**: Identifying players with excessive items
- **Inactive Data**: Old player data consuming unnecessary space
- **Fragmentation**: Database efficiency degradation over time

## 🛡️ Safety Features

- **Read-Only Analysis**: Never modifies your database
- **Error Handling**: Graceful handling of corrupted or locked databases
- **Backup Reminders**: Automatic recommendations for database backups
- **Non-Destructive**: All operations are analysis-only

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
- Additional export formats (JSON, CSV, etc.)

## 📜 License

This project is open source. Feel free to modify and distribute according to your needs.

## ⚠️ Disclaimer

This tool is for analysis purposes only. Always backup your database before performing any maintenance operations. The analyzer does not modify your database but provides recommendations for manual maintenance.

---

**Happy analyzing! 🎮**
