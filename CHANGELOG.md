# Changelog

All notable changes to this project will be documented in this file.

## [2.1.0] - 2026-03-17

### Added
- Created `config.json` for centralized version management.
- Added `CHANGELOG.md` to track project history.

### Fixed
- Fixed `QComboBox` dropdown menu transparency issue on Windows by using explicit `QListView` and solid black background.
- Fixed `QCalendarWidget` month/year dropdown transparency by forcing opaque background-color in QSS.

## [2.0.0] - 2026-03-10

### Added
- Complete UI overhaul with Dark/Neon theme.
- Support for XML and PDF invoice parsing.
- Automated Tax Code (MST) lookup via API.
- Support for multiple seller bank accounts.
- Professional Word document generation with watermarks.
