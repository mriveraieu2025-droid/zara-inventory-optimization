ZARA REPRODUCIBILITY PACKAGE — verified data and Python scripts

GitHub: open your private zara-inventory-optimization repository.
Choose Add file > Upload files. Drag the DATA and SRC folders (from this
unzipped package), and optionally requirements.txt and .gitignore.
Commit with message: Add audited input data and runnable baseline model.

If you clone/download the completed repository onto your computer, run:
    py -m pip install -r requirements.txt
    py src/verify_saved_results.py
    py src/solve_zara_final.py

These scripts read input CSVs from data/ and write baseline outputs to
results/. Unlike the earlier flat-folder versions, they do not expect
the CSVs next to the Python scripts.

IMPORTANT: model_settings.csv was reconstructed from documented settings;
compare it to the original data generator's settings when available.
These results are synthetic academic experiments, not Zara company data.
