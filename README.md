# heart-all
A simple script to save all tracks in a Spotify playlist to your library.

## Usage
1. Create a Spotify application at [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/applications)
2. Clone the repository using `git clone https://github.com/Temerold/heart-all.git`
3. Install the required packages using `pip install -r requirements.txt`
4. Run the script using `python heart_all.py`
5. Follow the instructions in the terminal
6. Enjoy!

### Configuration
You can configure the script by editing the `config.yaml` file. The following options are available:
- `log_filename`: The name of the log file
- `playlist_id`: The ID of the playlist you want to save

## Contributing
Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

### Code style
This project uses [Google's style guides](https://google.github.io/styleguide/) and uses [Black](https://black.readthedocs.io/en/stable/), [isort](https://pycqa.github.io/isort/), and [Pylint](https://pylint.readthedocs.io/en/latest/) to enforce them. Other tools are however welcome!

#### Changes made to the Google Python Style Guide
In accordance with the license used by the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) ([Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0)), all changes made to [`pylintrc`](pylintrc) have to be documented. The following changes have been made:
* `max-line-length` has been changed from 80 to 88
