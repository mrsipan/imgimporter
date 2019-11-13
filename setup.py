from setuptools import setup, find_packages

extras_require = {
    'test': ['mock', 'pytest']
    }

entry_points = '''
[console_scripts]
imgimporter = imgimporter:main
'''

setup(
    name='imgimporter',
    version='0.0.1',
    install_requires=[
        'boto3',
        'pytest-mock',
        ],
    py_modules=['imgimporter'],
    package_dir={'': '.'},
    description='imgimporter',
    zip_safe=False,
    extras_require=extras_require,
    tests_require=extras_require['test'],
    entry_points=entry_points,
    )

