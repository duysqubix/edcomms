from distutils.core import setup
setup(
    name='edcomms',
    packages=['edcomms'],
    version='0.1.2',
    license=
    'Closed',  # Chose a license from here: https://help.github.com/articles/licensing-a-repository
    description=
    'Universal Communications library used in EagleDaddy products',  # Give a short description about your library
    author='duanuys',  # Type in your name
    author_email='duys@qubixat.com',  # Type in your E-Mail
    url=
    'https://github.com/duysqubix/edcomms',  # Provide either the link to your github or to your website
    # download_url=
    # 'https://github.com/user/reponame/archive/v_01.tar.gz',  # I explain this later on
    keywords=['comms', 'mqtt',
              'eagledaddy'],  # Keywords that define your package best
    install_requires=[  # I get to this in a second
        'paho-mqtt',
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',  # Chose either "3 - Alpha", "4 - Beta" or "5 - Production/Stable" as the current state of your package
        'Intended Audience :: Developers',  # Define that your audience are developers
        'Topic :: Software Development :: Build Tools',
        'Programming Language :: Python :: 3.7',
    ],
)