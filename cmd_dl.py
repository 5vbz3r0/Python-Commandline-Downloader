import re, os, sys, argparse, time
import requests
from bs4 import BeautifulSoup as bs
from base64 import b64decode
from functools import partial
# from itertools import count, izip
from urllib.parse import urlparse
from multiprocessing.dummy import Pool

def download(url, filename, reporthook=None):
	blocksize = 4096
	trial = 0
	try:
		dl_length = os.path.getsize(filename)
		count = dl_length // blocksize
	except FileNotFoundError:
		dl_length = 0
		count = 0
	code = -1
	s = requests.Session()
	headers =  {'user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36',
				'connection':'keep-alive', 'range':'bytes={}-'.format(dl_length)}
	# headers =  {'user-agent':'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36',
	# 			'connection':'keep-alive', 'range':'bytes={}-'.format(dl_length)}
	s.headers.update(headers)
	try:
		r = s.get(url, stream=True, timeout=10)
	except requests.exceptions.Timeout:
		print('\nTimeout\n')
		s.close()
		return 3
	if r.status_code == requests.codes.forbidden:
		raise requests.exceptions.HTTPError('{}'.format(r.status_code))
	# if not os.path.exists(filename): write_code = 'wb'
	if r.status_code == requests.codes.partial:
		write_code = 'ab'
	elif r.status_code == requests.codes.ok and count != 0:
		print("Unable to resume download. Redownloading entire file.")
		write_code = 'wb'
	final_ext = r.headers['content-type'].split('/')[1]
	final_filename = '{}.{}'.format('.'.join(filename.split('.')[:-1]), final_ext)
	if os.path.exists(final_filename):
		code = 0
		return code
	totalsize = int(r.headers['Content-Length']) + dl_length
	try:
		with open(filename, write_code) as f:
			for chunk in r.iter_content(chunk_size=blocksize):
				v = f.write(chunk)
				if reporthook is not None: reporthook(count, blocksize, totalsize)
				count += 1
	except requests.exceptions.Timeout:
		write_code = 'ab'
		print('\nTimeout\n')
		code = 2
	except requests.exceptions.ConnectionError:
		write_code = 'ab'
		print('\nConnection error\n')
		code = 2
	except requests.exceptions.StreamConsumedError:
		write_code = 'ab'
		print('\nConnection error\n')
		code = 2
	except Exception as err:
		print(err)
	else:
		os.rename(filename, final_filename)
		code = 1
	finally:
		s.close()
		return code

def download_episode(url, title, folder):
	trial = 1
	title = re.sub(r"[^a-zA-Z0-9\-\.\(\)\' ]", '_', title)
	filename = title + '.part'
	filename = '{}/{}'.format(folder, filename)
	err = None
	while True:
		if os.path.exists(filename): print('Continuing download of {}'.format(title))
		else: print('Downloading {}'.format(title))
		surl = url
		while surl is not None:
			try:
				dl_complete = download(surl, filename=filename, reporthook=dlProgress)
			except requests.exceptions.HTTPError as e:
				err = e
				print("\nUnable to download..\n"+str(err))
				if '403' in str(e):
					trial+=1
					if trial > 10:
						return
					print("Trying again..\nTry: " + str(trial))
					continue
				else:
					break
			else:
				if dl_complete == 0: print('\nFile already exists. Skipping download.\n')
				elif dl_complete == 1: print("\nDownload complete\n")
				elif dl_complete == 2: print("\nUnable to complete download due to bad connection\n")
				elif dl_complete == 3: print("\nUnable to connect to the server\n")
				return
		trial += 1
		if trial > 10:
			return
		print("\nUnable to download..\n" + str(err))
		print("Trying again..\nTry: " + str(trial))

def dlProgress(count, blockSize, totalSize):
	global init_count
	global time_history
	try:
		time_history.append(time.monotonic())
	except NameError:
		time_history = [time.monotonic()]
	try:
		init_count
	except NameError:
		init_count = count
	percent = count*blockSize*100/totalSize
	if totalSize-count*blockSize <= 40000:
		percent = 100
	dl, dlu = unitsize(count*blockSize)
	tdl, tdlu = unitsize(totalSize)
	count -= init_count
	if count > 0:
		n = 1000
		_count = n if count > n else count
		time_history = time_history[-_count:]
		time_weights = list(range(1,len(time_history)-1))
		time_diff = [(i-j)*k for i, j, k in zip(time_history[1:], time_history[:-1], time_weights)]
		try:
			speed = blockSize*(sum(time_weights)) / sum(time_diff)
		except:
			speed = 0
	else: speed = 0
	n = int(percent//4)
	try:
		eta = format_time((totalSize-blockSize*(count+init_count+1))//speed)
	except:
		eta = '>1 day'
	speed, speedu = unitsize(speed, True)
	l = len(tdl)-len(dl)
	sys.stdout.write("\r" + "   {:.2f}".format(percent) + "% |" + "#"*n + " "*(25-n) + "| " + " "*(l+1) + dl + dlu  + "/" + tdl + tdlu + speed + speedu + " " + eta)
	sys.stdout.flush()

def unitsize(size, speed=False):
	B = 'B' if not speed else 'B/s'
	unit = ''
	if size<1024:
		unit = B + ' '
	elif (size/1024) < 1024:
		size /= 1024.0
		unit = 'k' + B
	elif (size/1024) < 1024**2:
		size /= 1024.0**2
		unit = 'M' + B
	else:
		size /= 1024.0**3
		unit = 'G' + B
	if speed: t = "{:4}.{:02}".format(int(size), int((size%1)*100))
	else: t = "{:.2f}".format(size)
	return t, unit

def format_time(t):
	sec = t = int(t)
	mn, hr = 0, 0
	if t>=60:
		sec=int(t%60)
		if sec<0: sec=0
		t //= 60
	else: return ("{:2}:{:02}:{:02}".format(hr, mn, sec))
	mn = t
	if t>=60:
		mn=int(t%60)
		t //= 60
	else: return ("{:2}:{:02}:{:02}".format(hr, mn, sec))
	hr = t
	if t>=24:
		hr=int(t%24)
		t //= 24
	else: return ("{:2}:{:02}:{:02}".format(hr, mn, sec))
	return '>1 day  '

def get_arguments():
	class join(argparse.Action):
		def __call__(self, parser, namespace, values, option_string=None):
			if option_string is None:
				values = ' '.join(values)
				if values in ['-h','--help']:
					parser.print_help()
			setattr(namespace, self.dest, values)
	parser = argparse.ArgumentParser(description='A command line script to download videos')
	parser.add_argument('-o', default=os.getcwd(), metavar='Download Folder')
	# parser.add_argument('--quality', choices=['1080p', '720p', '480p', '360p'], default='1080p')
	# parser.add_argument('--eps', default=[-1], help=episodes_help, type=str, action=join)
	parser.add_argument('url', nargs=argparse.REMAINDER, action=join, help='URL')
	args = parser.parse_args()
	if args.url is '':
		print("Please enter url")
		parser.print_help()
		exit()
	return args.o, args.url#, args.quality, args.eps

def main():
	folder, url = get_arguments()
	print(url)
	title = url.split('/')[-1]
	try:
		title = title.split('?')[0]
	except ValueError:
		pass
	download_episode(url, title, folder)

if __name__ == '__main__':
	main()