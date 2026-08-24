# Contributing to PaperBlast

## Local Development
1. Install Python dependencies: `pip install -r requirements.txt`
2. Install Node dependencies: `npm install`
3. Run the tests: `npm test` or `pytest server/tests/`
4. Start the local server: `npm run dev`

## Code Standards
- Ensure all tests pass.
- New agent tools must define explicit JSON schemas in `server/engine/tools.py`.
- Do not introduce in-memory persistence globals. Use the `DatabaseProvider` interface.
