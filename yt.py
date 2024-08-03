import os
from pytube import Playlist
from moviepy.editor import *


music_folder_path = "music-yt/"

def prompt_exists_action():
    """ask the user what happens if the file being downloaded already exists"""
    global file_exists_action
    if file_exists_action == "SA":  # SA == 'Skip All'
        return False
    elif file_exists_action == "RA":  # RA == 'Replace All'
        return True
    
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


link = input("Enter YouTube Playlist URL: ✨")

yt_playlist = Playlist(link)

folderName = make_alpha_numeric(yt_playlist.title)
os.mkdir(folderName)

totalVideoCount = len(yt_playlist.videos)
print("Total videos in playlist: 🎦", totalVideoCount)

for index, video in enumerate(yt_playlist.videos, start=1):
    audio = download_yt(video,video.title)

    # print("Downloading:", video.title)
    # video_size = video.streams.get_highest_resolution().filesize
    # print("Size:", video_size // (1024 ** 2), "🗜 MB")
    # video.streams.get_highest_resolution().download(output_path=folderName)
    # print("Downloaded:", video.title, "✨ successfully!")
    # print("Remaining Videos:", totalVideoCount - index)

print("All videos downloaded successfully! 🎉")