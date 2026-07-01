name: Raport saptamanal TreidingSB

# Ruleaza in fiecare LUNI la 06:00 UTC (inainte de deschiderea sesiunii Londra)
# Rezultat: raport-YYYY-MM-DD.pdf in reports/Q{N}_YYYY/
on:
  schedule:
    - cron: '0 6 * * 1'    # minutul 0, ora 6, orice zi, orice luna, LUNI (1)
  workflow_dispatch:
    inputs:
      nota:
        description: 'Motiv regenerare manuala (optional)'
        required: false
        default: 'Regenerare manuala'

permissions:
  contents: write

jobs:
  raport-saptamanal:
    runs-on: ubuntu-latest
    steps:
      - name: Descarca codul
        uses: actions/checkout@v4

      - name: Configureaza Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Instaleaza dependinte
        run: pip install -r scripts/requirements.txt

      - name: Genereaza raportul PDF saptamanal
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python scripts/generate_report.py

      - name: Publica raportul pe repository
        run: |
          git config user.name "TreidingSB Bot"
          git config user.email "bot@treidingsb.local"
          git add reports/
          git diff --staged --quiet || git commit -m "Raport saptamanal $(date -u +%Y-%m-%d) - ${{ github.event.inputs.nota || 'Generare automata luni' }}"
          git push
