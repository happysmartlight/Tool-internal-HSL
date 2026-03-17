# Changelog

All notable changes to this project will be documented in this file.

## [2.2.0] - 2026-03-17

### Added
- Implemented exclusive support for HTML draft invoices (specifically 1C template).
- Added `beautifulsoup4` and `lxml` as core dependencies for robust HTML parsing.
- Refined parsing logic to handle row-spanned totals and fragmented item tables.

### Changed
- Updated UI text and file dialog filter to restrict support to HTML format only.
- Enhanced address extraction with multiple field lookahead barriers.

### Fixed
- Fixed address parsing overflow issue where buyer address captured subsequent field labels.

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
