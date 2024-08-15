import os
from pytube import Playlist
from moviepy.editor import *
from mutagen.easyid3 import EasyID3
import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from mutagen.id3 import APIC, ID3
import urllib.request
from tqdm import tqdm
import gradio as gr
from tkinter import Tk, filedialog
from dotenv import load_dotenv


file_exists_action=""
music_folder_path = "music-yt/"   # path to save the downloaded music
# SPOTIPY_CLIENT_ID = "" # Spotify API client ID  # keep blank if you dont need spotify metadata
# SPOTIPY_CLIENT_SECRET = ""  # Spotify API client secret

def prompt_exists_action():
    """ask the user what happens if the file being downloaded already exists"""
    global file_exists_action
    if file_exists_action == "SA":  # SA == 'Skip All'
        return False
    elif file_exists_action == "RA":  # RA == 'Replace All'
        return True
    
    print("This file already exists.")
    while True:
        resp = (
            input("replace[R] | replace all[RA] | skip[S] | skip all[SA]: ")
            .upper()
            .strip()
        )
        if resp in ("RA", "SA"):
            file_exists_action = resp
        if resp in ("R", "RA"):
            return True
        elif resp in ("S", "SA"):
            return False
        print("---Invalid response---")
    
def make_alpha_numeric(string):
    return ''.join(char for char in string if char.isalnum())

def download_yt(yt,search_term):
    """download the video in mp3 format from youtube"""
    # remove chars that can't be in a windows file name
    yt.title = "".join([c for c in yt.title if c not in ['/', '\\', '|', '?', '*', ':', '>', '<', '"']])
    # don't download existing files if the user wants to skip them
    exists = os.path.exists(f"{music_folder_path}{yt.title}.mp3")
    if exists and not prompt_exists_action():
        return False

    # download the music
    max_retries = 3
    attempt = 0
    video = None

    while attempt < max_retries:
        try:
            video = yt.streams.filter(only_audio=True).first()
            if video:
                break
        except Exception as e:
            print(f"Attempt {attempt + 1}  {search_term} failed due to: {e}")
            attempt += 1
    if not video:
        print(f"Failed to download {search_term}")
        # check if a file named failed_downloads.txt exists if not create one and append the failed download
        if not os.path.exists("failed_downloads.txt"):
            with open("failed_downloads.txt", "w") as f:
                f.write(f"{search_term}\n")
        else:
            with open("failed_downloads.txt", "a") as f:
                f.write(f"{search_term}\n")
        return False
    vid_file = video.download(output_path=f"{music_folder_path}tmp")
    # convert the downloaded video to mp3
    base = os.path.splitext(vid_file)[0]
    audio_file = base + ".mp3"
    mp4_no_frame = AudioFileClip(vid_file)
    mp4_no_frame.write_audiofile(audio_file, logger=None)
    mp4_no_frame.close()
    os.remove(vid_file)
    os.replace(audio_file, f"{music_folder_path}tmp/{yt.title}.mp3")
    audio_file = f"{music_folder_path}tmp/{yt.title}.mp3"

    return audio_file

def set_metadata(metadata, file_path):
    """adds metadata to the downloaded mp3 file"""

    mp3file = EasyID3(file_path)

    # add metadata
    mp3file["albumartist"] = metadata["artist_name"]
    mp3file["artist"] = metadata["artists"]
    mp3file["album"] = metadata["album_name"]
    mp3file["title"] = metadata["track_title"]
    mp3file["date"] = metadata["release_date"]
    mp3file["tracknumber"] = str(metadata["track_number"])
    mp3file["isrc"] = metadata["isrc"]
    mp3file.save()

    # add album cover
    audio = ID3(file_path)
    with urllib.request.urlopen(metadata["album_art"]) as albumart:
        audio["APIC"] = APIC(
            encoding=3, mime="image/jpeg", type=3, desc="Cover", data=albumart.read()
        )
    audio.save(v2_version=3)

def search_spotify(search_term : str, sp)->str:
    """search for the track on spotify"""
    search_results = sp.search(search_term, type="track", limit=1)
    if search_results["tracks"]["total"] == 0:
        return None
    track = search_results["tracks"]["items"][0]
    return track["external_urls"]["spotify"]

def get_track_info_spotify(track_url,sp):
    res = requests.get(track_url)
    if res.status_code != 200:
        # retry 3 times
        for i in range(3):
            res = requests.get(track_url)
            if res.status_code == 200:
                break
    if res.status_code != 200:
        print("Invalid Spotify track URL")

    track = sp.track(track_url)

    track_metadata = {
        "artist_name": track["artists"][0]["name"],
        "track_title": track["name"],
        "track_number": track["track_number"],
        "isrc": track["external_ids"]["isrc"],
        "album_art": track["album"]["images"][1]["url"],
        "album_name": track["album"]["name"],
        "release_date": track["album"]["release_date"],
        "artists": [artist["name"] for artist in track["artists"]],
    }

    return track_metadata

def get_track_info_youtube(video):

    track_metadata = {
        "artist_name": video.author,
        "track_title":  video.title,
        "track_number": 0,
        "isrc": "",
        "album_art": video.thumbnail_url,
        "album_name": video.author,
        "release_date": video.publish_date.strftime("%Y-%m-%d"),
        "artists": [video.author],
    }

    return track_metadata

def greet(name, intensity):
    return "Hello, " + name + "!" * int(intensity)

def ensure_folder_path_ends_with_slash(folder_path):
    if not folder_path.endswith(os.sep):
        folder_path += os.sep
    return folder_path

def folder_select():
    global music_folder_path
    filename = filedialog.askdirectory()
    root = Tk()
    root.attributes("-topmost", True)
    root.withdraw()
    if filename:
        if os.path.isdir(filename):
            root.destroy()
            music_folder_path = ensure_folder_path_ends_with_slash(str(filename))
            return music_folder_path
        else:
            root.destroy()
            music_folder_path = ensure_folder_path_ends_with_slash(str(filename))
            return music_folder_path
    else:
        filename = "Folder not seleceted"
        root.destroy()
        music_folder_path = ensure_folder_path_ends_with_slash(str(filename))
        return music_folder_path
    

def downloader(link,exists_action, progress=gr.Progress()):
    custom_labels = {
        "Replace all": "RA",
        "Skip all": "SA",
        "Determine while downloading from CLI": "",
    }
    global file_exists_action 
    file_exists_action = custom_labels[exists_action]
    use_spotify_for_metadata = True
    try:
        load_dotenv()
        SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
        SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
        client_credentials_manager = SpotifyClientCredentials(
            client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET
        )
        sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
    except Exception as e:
        use_spotify_for_metadata = False
        print(f"Failed to connect to Spotify API: {e}")
        print("Continuing without Spotify API, some song metadata will not be added")
    # link = input("Enter YouTube Playlist URL: ✨")

    yt_playlist = Playlist(link)



    totalVideoCount = len(yt_playlist.videos)
    print("Total videos in playlist: 🎦", totalVideoCount)

    for index, video in enumerate(progress.tqdm(yt_playlist.videos,desc= "downloading..."), start=1):
        try:
            print("Downloading: "+video.title)
            audio = download_yt(video,video.title)
            if audio:
                if(use_spotify_for_metadata):
                    try:
                        track_url = search_spotify(f"{video.author} {video.title}",sp)
                    except Exception as e:
                        print(e)
                        track_url = None
                    if not track_url:
                        track_info = get_track_info_youtube(video)
                    else:
                        track_info = get_track_info_spotify(track_url,sp)
                else:
                    track_info = get_track_info_youtube(video)

                set_metadata(track_info, audio)
                os.replace(audio, f"{music_folder_path}{os.path.basename(audio)}")
        except Exception as e:
            print(f"Failed to download {video.title} due to: {e}")
            continue

    print("All videos downloaded successfully!")
    return "All videos downloaded successfully!"

def save_app_settings(spotify_client_id,spotify_client_secret):
    try:
        env_str="SPOTIPY_CLIENT_ID="+spotify_client_id+"\nSPOTIPY_CLIENT_SECRET="+spotify_client_secret
        with open(".env", "r+") as f:
            f.write(env_str)
    except Exception as e:
        print (e)
        return "app settings update failed"
    return "app settings updated"

def ui():
    with gr.Blocks() as gui:
        gr.Markdown ("""
            <table style="border: none; padding: 0;">
                <tr style="border: none; padding: 0;">
                    <td style="border: none; padding: 0;">
                    <a href="https://github.com/Predacons"><img src="https://i.postimg.cc/MKMHRy7Q/acf160a0-f299-45db-ba77-309079191f6b-removebg-preview.png" width="60px" height="60px"></a>
                    </td>
                    <td style="border: none; padding: 10; vertical-align: middle;">
                    <a href="https://github.com/Predacons" style="text-decoration: none;"><H1>Playlist downloader<H1></a>
                    </td>
                </tr>
            </table>""")
        with gr.Tab(label="Youtube"):
            gr.Markdown("""
            <table style="border: none; padding: 0;">
                <tr style="border: none; padding: 0;" >
                    <td style="border: none; padding: 0;">
                    <a href="https://github.com/Predacons"><img src="https://www.gstatic.com/youtube/img/promos/growth/07a2a04c83a46863bd8bb1f316bfcb7ba3d46899d515a605f89a76a254c235d2_244x112.webp" width="160px" height="60px"></a>
                </tr>
            </table>""")
            with gr.Row():
                image_browse_btn = gr.Button("Select output directory", min_width=1)
                input_path = gr.Textbox(label="output directory path", scale=5, interactive=False)
                image_browse_btn.click(folder_select, inputs=[], outputs=input_path, show_progress="hidden")
            with gr.Row():
                yt_playlist = gr.Textbox(label="Youtube playlist url")
            with gr.Row():
                file_exists_action = gr.Radio(["Replace all", "Skip all", "Determine while downloading from CLI"], label="Song Exist Action", info="What to do when that song already exist in your directory?")
            with gr.Row():
                download_btn = gr.Button("Download playlist")
            with gr.Row():
                progress_bar = gr.Textbox()
                download_btn.click(downloader, inputs=[yt_playlist,file_exists_action], outputs=[progress_bar])
            gr.Markdown ("""
                        <p style="text-align: center; font-size: small;">Buy <a href="https://www.youtube.com/premium">YouTube Premium</a> to get similar features</a> </p>
                        """)    
        with gr.Tab(label="App settings"):
            gr.Markdown("# App Settings")
            with gr.Row():
                SPOTIPY_CLIENT_ID = gr.Textbox(label="Spotify client id")
                SPOTIPY_CLIENT_SECRET = gr.Textbox(label="Spotify client secret")
            with gr.Row():
                save_appsettings_button = gr.Button("Update app settings")
            with gr.Row():
                app_settings_update = gr.Textbox(label= "")
                save_appsettings_button.click(save_app_settings,inputs=[SPOTIPY_CLIENT_ID,SPOTIPY_CLIENT_SECRET],outputs=app_settings_update)

        gr.Markdown ("""
                        <p style="text-align: center; font-size: small;">Support artists. Buy music. Attend concerts. 🎵✨</a> </p>
                        <p style="text-align: center; font-size: small;"><a href="https://github.com/shouryashashank">Shourya Shashank</a> </p>
                        <p style="text-align: center; font-size: small;">Support me on <a href="https://patreon.com/Predacons?utm_medium=clipboard_copy&utm_source=copyLink&utm_campaign=creatorshare_creator&utm_content=join_link">Patreon</a> </p> 
                     """)    

    return gui

def main():
    print("Abracadabra!")
    webapp = ui()
    webapp.launch()
    



if __name__ == "__main__":
    main()
