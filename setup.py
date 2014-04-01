"""
Mercantile setup.
"""

from setuptools import setup, find_packages

setup( name='mercantile',
       version='0.1',
       description='Webserver mangement via fabric scripts.',
       author='Brantley Harris',
       author_email='deadwisdom@gmail.com',
       packages = find_packages(),
       include_package_data = False,
       zip_safe = True
      )
