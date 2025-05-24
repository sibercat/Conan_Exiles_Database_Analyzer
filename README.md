# 🏛️ Conan Exiles Database Analyzer Suite

**By: Sibercat**

A comprehensive Python toolkit for analyzing and maintaining Conan Exiles `game.db` SQLite databases with enterprise-grade safety features.

## 🚀 Key Features

- **📊 Complete Database Health Analysis** - Structure, size, fragmentation, and performance monitoring
- **🎮 Game Events Analysis** - 100+ event types with activity patterns and cleanup recommendations  
- **🎒 Item Inventory Analysis** - Player rankings, storage patterns, and item distribution
- **🏥 Database Health & Safety** - Prevents destructive cleanup that destroys player chests
- **🗑️ Events Cleanup Manager** - Smart event cleanup with backup integration
- **🔍 Interactive SQL Console** - Safe database exploration with read-only queries

## 📁 Project Structure

```
├── ConanExiles_SQLite_Database_Analyzer.py    # Main controller & menu system
├── SQLite_Game_Events.py                      # Game events specialist
├── SQLite_Item_table.py                       # Inventory specialist  
├── SQLite_Orphaned_Items_Analysis.py          # Database health specialist
├── SQLite_Events_CleanUp.py                   # Events cleanup manager
└── README.md                                  # This documentation
```

## 🛠️ Installation

```bash
# Install dependencies
pip install prettytable

# Run analyzer
python ConanExiles_SQLite_Database_Analyzer.py
```

### Command Line Options
```bash
# Run all analyses
python ConanExiles_SQLite_Database_Analyzer.py --auto

# Safe cleanup with preview
python ConanExiles_SQLite_Database_Analyzer.py --cleanup --dry-run

# Clean events older than 30 days
python ConanExiles_SQLite_Database_Analyzer.py --events-cleanup 30
```

## 🎯 Main Menu Options

1. **📋 General Database Analysis** - Complete health check
2. **🎮 Game Events Analysis** - Event logging analysis with visualizations
3. **🎒 Item Inventory Analysis** - Player inventory deep-dive
4. **🏥 Database Health Analysis** - **Critical: Detects cleanup damage and validates ownership**
5. **🔄 Complete Analysis Suite** - All analyses combined
6. **🧹 Database Cleanup** - Automated maintenance with safety checks
7. **🗑️ Events Cleanup Manager** - Advanced event cleanup with backups
8. **🔍 Interactive Query Mode** - SQL console for exploration
9. **📊 Export Results** - JSON/CSV export

## 🛡️ Revolutionary Safety Features

### ⚠️ Prevents Database Disasters
Most community cleanup scripts use this **DANGEROUS** approach:
```sql
-- ❌ DESTROYS ALL PLAYER CHESTS!
DELETE FROM item_inventory WHERE owner_id NOT IN (SELECT id FROM characters);
```

Our analyzer **prevents these disasters** by understanding that:
- **Character IDs** own personal inventory (hotbar, equipment)
- **Structure IDs** own external storage (chests, crafting stations)
- **Only missing IDs** are truly orphaned

### ✅ Safe Cleanup Example
```sql
-- ✅ SAFE: Only removes truly orphaned data
DELETE FROM item_inventory 
WHERE owner_id NOT IN (SELECT id FROM characters)      -- Not a character
AND owner_id NOT IN (SELECT id FROM actor_position);   -- Not a structure
```

### 🚨 Cleanup Damage Detection
```
🚨 CRITICAL: CLEANUP DAMAGE DETECTED!
❌ 15 active players lost external storage items!
✅ Recommended: Restore from backup or compensate players.
```

## 📊 Example Output

### Database Health Assessment
```
📊 Summary:
Existing Characters: 324
Existing Structures: 8,547  
Items in Structures: 89,234 ✅ NORMAL
Truly Orphaned Items: 142

✅ DATABASE HEALTH: EXCELLENT
🎉 No cleanup needed! All items are properly owned.
```

### Player Rankings
```
👥 TOP PLAYERS BY ITEM COUNT:
┌──────┬─────────────────────┬────────────┬─────────────────────────────┐
│ Rank │ Player Name         │ Item Count │ Inventory Types             │
├──────┼─────────────────────┼────────────┼─────────────────────────────┤
│  1   │ SiberCat            │ 15,847     │ Player Inventory, Chests +8 │
│  2   │ ConanFan42          │ 8,234      │ Equipment, Crafting Benches │
└──────┴─────────────────────┴────────────┴─────────────────────────────┘
```

## 📋 Requirements

- **Python**: 3.6+
- **Dependencies**: `prettytable` 
- **Database**: Conan Exiles `game.db` SQLite file
- **Compatibility**: All Conan Exiles versions, PvE/PvP/PvE-C

## 🔍 Common Issues

**High "Deleted Characters" Count**: Normal! Includes character respawns and server resets, not actual player departures.

**"Database Locked"**: Stop game server temporarily or copy database file for analysis.

**Performance**: Large databases (1GB+) may take 5-15 minutes for complete analysis.

## ⚠️ Safety Notice

**Always backup your database before any cleanup operations.**

This tool prevents the database disasters commonly seen in the Conan Exiles community by understanding the difference between character-owned items (personal inventory) and structure-owned items (chests, crafting stations).

**Never ignore safety warnings** - they prevent server-killing mistakes that destroy all player chests.

## 🤝 Contributing

We welcome contributions! Priority areas:
- Additional event type mappings
- Performance optimizations  
- Enhanced visualizations
- Multi-language support

---

**Professional database analysis for healthy Conan Exiles servers 🏛️**
