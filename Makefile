.PHONY: pipeline test dashboard

pipeline:
	PYTHONPATH=src python3 -m eventlab.scripts.run_pipeline

test:
	PYTHONPATH=src python3 -m unittest discover -s tests

dashboard:
	PYTHONPATH=src streamlit run src/eventlab/dashboard/streamlit_app.py

