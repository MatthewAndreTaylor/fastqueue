build:
	python3 ./setup.py install

clean:
	rm -rf `find . -name __pycache__`
	rm -rf *.egg-info
	rm -rf build