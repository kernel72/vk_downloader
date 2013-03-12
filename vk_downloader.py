__author__ = 'kernel72'

import sys
import os
import time
import getpass
import vk_api
import requests

from multiprocessing import Process, Manager, Lock
from argparse import ArgumentParser

LOGIN = ''
PASSWORD = ''
DOWNLOAD_DIR = ''
WORKERS_COUNT = 0
__CHUNK_SIZE = 1024


def init_params():
    global LOGIN, PASSWORD, DOWNLOAD_DIR, WORKERS_COUNT
    parser = ArgumentParser(description="Vk.com music playlist downloader.")
    parser.add_argument('vk_login', help='Your login (email or phone) to access vk.com')
    parser.add_argument('-t', '--threads', dest='threads', type=int, default=10,
                        help='Count of tracks to download simultaneously')
    parser.add_argument('-d', '--dir', dest='download_dir', help='Directory to place downloaded music')
    params = parser.parse_args()

    LOGIN = params.vk_login
    PASSWORD = getpass.getpass(prompt='Vk user password:')

    if not params.download_dir:
        DOWNLOAD_DIR = '%s_downloaded_music/' % LOGIN

    WORKERS_COUNT = params.threads


def connect_to_vk(login, password):
    try:
        connection = vk_api.VkApi(login, password)
    except vk_api.authorization_error, e:
        print e.message
        sys.exit(1)
    return connection


def get_filename(vk_audio):
    filename = "%s - %s.mp3" % (vk_audio['artist'], vk_audio['title'])
    filename = filename.replace('\\', '_').replace('/', '_')
    return filename


def get_url(vk_audio):
    return vk_audio['url']


def download_audio(filename, url, progress_list, downloaded_tracks, lock):
    global DOWNLOAD_DIR, __CHUNK_SIZE

    download_path = '%s/%s' % (DOWNLOAD_DIR, filename)

    if not os.path.exists(download_path):

        r = requests.get(url, stream=True)
        total_size = float(r.headers['content-length'])

        downloaded = 0

        with open(download_path, 'wb') as a:
            for chunk in r.iter_content(__CHUNK_SIZE):
                if not chunk:
                    break
                a.write(chunk)
                downloaded += len(chunk)
                progress_list[filename] = float(downloaded) / total_size

    del progress_list[filename]
    with lock:
        downloaded_tracks.value += 1
    return


def start_download_process(vk_audio, workers_list, progress_list, downloaded_tracks, lock):
    filename = get_filename(vk_audio)
    url = get_url(vk_audio)

    progress_list[filename] = 0.0
    download_process = Process(target=download_audio, args=(filename, url, progress_list, downloaded_tracks, lock))
    download_process.start()

    workers_list.append(download_process)
    return


def print_progress(progress, downloaded_tracks, total):
    sys.stdout.write('\033[2J\033[H') #clear screen
    for filename, percent in progress.items():
        bar = '[' + ('=' * int(percent * 20)).ljust(20) + '] '
        percent = '%5.1f %%' % float(percent * 100)
        sys.stdout.write("%s\n%s\n" % (filename, (bar + percent)))
    sys.stdout.write("\nDownloaded %s of %s\n" % (downloaded_tracks, total))
    sys.stdout.flush()
    return


def clean_workers(workers_list):
    for num, worker in enumerate(workers_list):
        if not worker.is_alive():
            del workers_list[num]
    return


def main():
    init_params()
    vk = connect_to_vk(LOGIN, PASSWORD)
    audio_list = vk.method('audio.get', {})

    total = len(audio_list)

    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    manager = Manager()
    workers_list = []
    progress_list = manager.dict()
    downloaded_tracks = manager.Value('i', 0)
    lock = Lock()

    for f in audio_list[:WORKERS_COUNT - 1]:
        start_download_process(f, workers_list, progress_list, downloaded_tracks, lock)

    del audio_list[:WORKERS_COUNT - 1]

    while any(worker.is_alive() for worker in workers_list) or len(audio_list):
        if audio_list and len(workers_list) < WORKERS_COUNT:
            f = audio_list.pop(0)
            start_download_process(f, workers_list, progress_list, downloaded_tracks, lock)
        print_progress(progress_list, downloaded_tracks.value, total)
        clean_workers(workers_list)
        time.sleep(0.1)
    print "Done!"

if __name__ == '__main__':
    main()
