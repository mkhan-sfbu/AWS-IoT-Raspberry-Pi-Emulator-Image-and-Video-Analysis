import signal
import cv2
import boto3
from contextlib import closing
import tempfile
import pygame
from botocore.exceptions import BotoCoreError, ClientError
import sys
import time
import os
import socket 
import fcntl
import struct
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from urllib.parse import parse_qs
import base64


# This will return video from the first webcam on your computer.
cap = cv2.VideoCapture(0)
#setting the buffer size and frames per second, to reduce frames in buffer
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
cap.set(cv2.CAP_PROP_FPS, 2)

session = boto3.Session(aws_access_key_id="...", aws_secret_access_key="...", region_name='us-east-1')

polly = session.client('polly')
rekognition = session.client('rekognition')

action = "detect"
if len(sys.argv)>2 : action = sys.argv[2]

interface='eth1'

def getIpAddress(ifname): 
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 
    return socket.inet_ntoa(fcntl.ioctl( 
        s.fileno(), 
        0x8915,  # SIOCGIFADDR 
        struct.pack(b'256s', bytes(ifname[:15], 'utf-8')) 
    )[20:24])

ipAddress=getIpAddress(interface)
print('Server IP Address: '+ipAddress)
serverPort=7328

dirname = os.path.dirname(__file__)
tmpDirectory = os.path.join(dirname, 'tmp-images')


class MyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        path, _, query_string = self.path.partition('?')
        if path != '/favicon.ico':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(bytes("<html><head><title>Simple Web Server to Show Image, Developed By SHKR</title></head><body>", "utf-8"))
            self.wfile.write(bytes("<p>Request: %s</p>" % self.path, "utf-8"))
            self.wfile.write(bytes("<p>Parsed Path: %s</p>" % path, "utf-8"))
            if path == '/':
                self.wfile.write(bytes("<p>This is a simple web server to show image.</p>", "utf-8"))
                self.wfile.write(bytes("<p>Temporary Directory: %s</p>" % tmpDirectory, "utf-8"))
            else:
                # need to show image!!!
                with open('{0}{1}.png'.format(tmpDirectory, path), 'rb') as image_file:
                    encoded_string = base64.b64encode(image_file.read())
                    self.wfile.write(bytes("<img src=\"data:image/jpg;base64,%s\" />" % encoded_string.decode('utf-8'), "utf-8"))
            self.wfile.write(bytes("</body></html>", "utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


webServer = None

if action=='learn':
    webServer = HTTPServer((ipAddress, serverPort), MyServer)
    print("Server configured at http://%s:%s" % (ipAddress, serverPort))
    daemon = threading.Thread(name='daemon_server', target=webServer.serve_forever)
    daemon.setDaemon(True) # Set as a daemon so it will be killed once the main thread is dead.
    daemon.start()

def destroyAndRelease():
    # Close the window / Release webcam
    cap.release()

    # De-allocate any associated memory usage
    cv2.destroyAllWindows()

    # close rekognition
    rekognition.close()

    # close polly
    polly.close()

    if webServer is not None: webServer.server_close()

    ##print("", end="\r", flush=True)
    ##print(" " * len(msg), end="", flush=True) # clear the printed line
    print("    ", end="\r", flush=True)


def handleExit(signum, frame):
    destroyAndRelease()
    sys.exit(1)
 
 
signal.signal(signal.SIGINT, handleExit)



def speakUpPolly(text2speak):
    try:
        # Request speech synthesis
        response = polly.synthesize_speech(Text=text2speak, OutputFormat="mp3", VoiceId="Joanna")
    except (BotoCoreError, ClientError) as error:
        # The service returned an error, exit gracefully
        print(error)
        sys.exit(-1)

    if "AudioStream" in response:
        with closing(response["AudioStream"]) as stream:
            output = os.path.join(tempfile.gettempdir(), "speech.mp3")
            # print("file stored into "+output)

            try:
                # Open a file for writing the output as a binary stream
                with open(output, "wb") as file:
                    file.write(stream.read())

                print("Polly speaking: "+text2speak)
                pygame.mixer.init()
                pygame.mixer.music.load(output)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy() == True:
                    continue

            except IOError as error:
                # Could not write to file, exit gracefully
                print(error)
                sys.exit(-1)

    else:
        # The response didn't contain audio data, exit gracefully
        print("Could not stream audio")
        sys.exit(-1)


if not cap.isOpened:
    speakUpPolly('Camera NOT Found!')
    print('--(!)Error opening video capture')
    destroyAndRelease()
    sys.exit(-1)



collectionId = "shkrtest"
if len(sys.argv)>1 : collectionId = sys.argv[1]
collections=rekognition.list_collections(MaxResults=10)
if not collectionId in collections['CollectionIds']:
    speakUpPolly('Collection '+collectionId+' NOT Found!')
    if action!='learn':
        destroyAndRelease()
        sys.exit(-1)
    # as we learning we need to create collection
    rekognition.create_collection(CollectionId=collectionId)
    speakUpPolly('Successfully Created Collection '+collectionId)


faceDirectory = os.path.join(dirname, 'faces')

faceCascade = cv2.CascadeClassifier(os.path.join(dirname, 'haarcascade_frontalface_default.xml'))


# loop runs if capturing has been initialized.
while(True):
    milli = int(round(time.time() * 1000))
    # reads frames from a camera
    frame = {}
    #calling read() twice as a workaround to clear the buffer.
    cap.read()
    cap.read()
    # ret checks return at each frame
    ret, frame = cap.read()

    if frame is None:
        speakUpPolly('No captured frame')
        print('--(!) No captured frame -- Break!')
        break

    timestr = time.strftime("%Y%m%d-%H%M%S")
    imgLocation = '{0}/image_{1}.png'.format(tmpDirectory, timestr)
    cv2.imwrite(imgLocation, frame)
    # Read the input image
    img = cv2.imread(imgLocation)
    # Convert into grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Detect faces
    faces = faceCascade.detectMultiScale(gray, 1.1, 4)
    if len(faces)>0:
        # imdata=cv2.imencode('.jpg', img)[1].tobytes()
        try: #match the captured imges against the indexed faces
            match_response = rekognition.search_faces_by_image(CollectionId=collectionId, Image={'Bytes': cv2.imencode('.jpg', img)[1].tobytes()}, FaceMatchThreshold=85)
            matches={}
            for p in match_response['FaceMatches']:
                matches[p['Face']['ExternalImageId']]=p['Face']['ExternalImageId']
            print('FaceMatches: '+str(len(matches))+' | cv2: '+str(len(faces)))
            if action=='learn' and len(matches)!=len(faces):
                # new face found! need to update our collection...
                for (x, y, w, h) in faces:
                    ROI = img[y:y+h, x:x+w]
                    nImgLoc = 'ni-{0}_x{1}y{2}w{3}h{4}'.format(timestr, x, y, w, h)
                    cv2.imwrite('{0}/{1}.png'.format(tmpDirectory, nImgLoc), ROI)
                    print("Visit http://%s:%s/%s" % (ipAddress, serverPort, nImgLoc))
                    speakUpPolly('Please input name for new person')
                    label=input('Name: ')
                    if len(label)>0:
                        idxResponse=rekognition.index_faces(CollectionId=collectionId,
                                    Image={'Bytes': cv2.imencode('.jpg', ROI)[1].tobytes()},
                                    ExternalImageId=label,
                                    MaxFaces=1,
                                    QualityFilter="AUTO",
                                    DetectionAttributes=['ALL'])
                        print('FaceId: ', idxResponse['FaceRecords'][0]['Face']['FaceId'])
                    else:
                        print('%s ignored' % nImgLoc)


            if len(matches)>0:
                for prsn in matches:
                    faceImgLocation = '{0}/{1}_{2}.png'.format(faceDirectory, prsn, timestr)
                    cv2.imwrite(faceImgLocation, frame)
                    print('Hello, ', prsn)
                    speakUpPolly('Hello, '+prsn+'! How are you?')
            else:
                speakUpPolly('No faces matched!')
                print('No faces matched')
        except:
            print('No face detected '+str(milli)+' | file: '+imgLocation)
    else:
        print('No Face Found. Waiting for someone...')


destroyAndRelease()
