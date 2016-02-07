from setuptools import setup

setup(
    name="stockist",
    version='1.0',
    py_modules=['app', 'stockist'],
    install_requires=[
        'Click',
    ],
    entry_points='''
        [console_scripts]
        stockist=app:cli
    ''',
)

