# Aerospace Job Hunter

An automated job scraper for aerospace industry internships and co-ops. This tool searches job boards across leading aerospace companies and filters listings to find relevant opportunities in your target specializations.

## Features

- **Multi-Platform Support**: Scrapes job listings from multiple job board providers:
  - Greenhouse
  - Lever
  - Workday
  - IBM BrassRing
  - SuccessFactors
  - Phenom

- **Smart Filtering**: Automatically identifies internships and co-ops in aerospace roles by:
  - Detecting internship-related keywords (internship, co-op, trainee, etc.)
  - Matching aerospace-specific technical keywords (propulsion, guidance, navigation, avionics, etc.)

- **Duplicate Prevention**: Tracks seen jobs locally to avoid redundant notifications

- **Robust Retries**: Uses exponential backoff to handle network failures gracefully

## Supported Companies

### Launch Providers & Spacecraft
- SpaceX
- Blue Origin
- Rocket Lab
- Relativity Space
- Firefly Aerospace
- Stoke Space
- ABL Space Systems
- Impulse Space
- Vast
- Axiom Space

### Satellites, Data & Communications
- Planet
- Astranis
- Capella Space
- HawkEye 360
- Slingshot Aerospace

### Aerospace Defense & Autonomy
- Anduril
- Shield AI
- True Anomaly
- Skydio
- Palantir

### Hypersonics & Next-Gen Aviation
- Hermeus
- Joby Aviation
- Archer Aviation
- Beta Technologies

### Defense & Aerospace Contractors
- Boeing
- Northrop Grumman
- RTX (Raytheon/Collins)
- Airbus
- GE Aerospace
- Lockheed Martin
- Gulfstream
- Bombardier
- L3Harris
- BAE Systems

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package installer)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd "Aerospace Job Hunter"
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Running the Scraper

```bash
python main.py
```

This will:
1. Query all supported aerospace company job boards
2. Filter for internships/co-ops matching aerospace keywords
3. Track new and previously seen jobs
4. Store persistent job data for future runs

### Configuration

Edit the `AEROSPACE_KEYWORDS` and `COMPANIES` lists in `main.py` to:
- Add or remove aerospace specializations you're interested in
- Include or exclude specific companies

## Testing

Run the test suite to verify functionality:

```bash
python -m pytest tests/test_main.py
```

Or using unittest:

```bash
python -m unittest tests.test_main
```

### Test Coverage

- Role matching logic (aerospace keyword detection)
- Internship pattern recognition
- Duplicate job handling
- API integration

## Dependencies

- **httpx** (>=0.27.0): Async HTTP client for efficient job board queries
- **tenacity** (>=8.2.0): Retry logic with exponential backoff for resilient API calls
- **beautifulsoup4** (>=4.15.0): HTML parsing for job board content extraction

## Architecture

### Key Components

- `is_target_role()`: Filters jobs based on title keywords
- `process_jobs()`: Deduplicates and validates new job listings
- `fetch_*_jobs()`: Provider-specific scrapers (Greenhouse, Lever, Workday, etc.)
- Persistence layer: Local JSON tracking of seen jobs

### Keyword Categories

- **Internship Terms**: internship, co-op, trainee, student
- **Aerospace Specializations**: aerospace, space, rocket, propulsion, structures, guidance/navigation/control (GNC), avionics, satellite, flight software, and more

## Contributing

Contributions welcome! To add support for new companies or job boards:

1. Add company configuration to the `COMPANIES` list
2. Implement a provider-specific scraper function
3. Add corresponding tests to `tests/test_main.py`

## License

[Add license information here]

## Notes

- Job boards may have rate limits; the retry logic includes exponential backoff
- Run periodically (e.g., daily) via cron or task scheduler to catch new listings
- Update the `AEROSPACE_KEYWORDS` list as new specializations emerge

## Support

For issues or suggestions, please open an issue in the repository.
