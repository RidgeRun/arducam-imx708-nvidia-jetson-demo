#!/usr/bin/env python3

import time
from pygstc.gstc import *

# Create PipelineEntity object to manage each pipeline
class PipelineEntity(object):
    def __init__(self, client, name, description):
        self._name = name
        self._description = description
        self._client = client
        print("Creating pipeline: " + self._name)
        self._client.pipeline_create(self._name, self._description)
    def play(self):
        print("Playing pipeline: " + self._name)
        self._client.pipeline_play(self._name)
    def stop(self):
        print("Stopping pipeline: " + self._name)
        self._client.pipeline_stop(self._name)
    def delete(self):
        print("Deleting pipeline: " + self._name)
        self._client.pipeline_delete(self._name)
    def eos(self):
        print("Sending EOS to pipeline: " + self._name)
        self._client.event_eos(self._name)
    def set_file_location(self, location):
        print("Setting " + self._name + " pipeline recording/snapshot location to " + location);
        filesink_name = "filesink_" + self._name;
        self._client.element_set(self._name, filesink_name, 'location', location);
    def listen_to(self, sink):
        print(self._name + " pipeline listening to " + sink);
        self._client.element_set(self._name, self._name + '_src', 'listen-to', sink);

pipelines_base = []
pipelines_video_rec = []
pipelines_video_enc = []
pipelines_snap = []

# Create GstD Python client
client = GstdClient()

# Create camera pipelines
camera0 = PipelineEntity(client, 'camera0', 'nvarguscamerasrc sensor-id=0 name=video ! \
video/x-raw(memory:NVMM),width=4608,height=2592,framerate=14/1,format=NV12 ! nvvidconv \
! video/x-raw(memory:NVMM),width=1920,height=1080 ! interpipesink name=camera_src0 \
forward-eos=true forward-events=true async=true sync=false')
pipelines_base.append(camera0)

camera0_rgba_nvmm = PipelineEntity(client, 'camera0_rgba_nvmm', 'interpipesrc \
listen-to=camera_src0 ! nvvideoconvert ! \
video/x-raw(memory:NVMM),format=RGBA,width=1920,height=1080 ! queue ! interpipesink \
name=camera0_rgba_nvmm forward-events=true forward-eos=true sync=false \
caps=video/x-raw(memory:NVMM),format=RGBA,width=1920,height=1080,pixel-aspect-ratio=1/1,\
interlace-mode=progressive,framerate=14/1')
pipelines_base.append(camera0_rgba_nvmm)

# Create Deepstream pipeline
deepstream = PipelineEntity(client, 'deepstream', 'interpipesrc listen-to=camera0_rgba_nvmm \
! nvstreammux0.sink_0 nvstreammux name=nvstreammux0 batch-size=2 batched-push-timeout=40000 \
width=1920 height=1080 ! queue ! nvinfer batch-size=2 \
config-file-path=../deepstream-models/dstest1_pgie_config.txt ! \
queue ! nvtracker ll-lib-file=../deepstream-models/libnvds_nvmultiobjecttracker.so \
enable-batch-process=true ! queue ! nvmultistreamtiler width=1920 height=1080 rows=1 \
columns=1 ! nvvideoconvert ! nvdsosd ! queue ! interpipesink name=deep forward-events=true \
forward-eos=true sync=false')
pipelines_base.append(deepstream)

# Create display pipeline
display = PipelineEntity(client, 'display', 'interpipesrc listen-to=deep ! \
nvvideoconvert ! nvegltransform ! nveglglessink sync=false')
pipelines_base.append(display)

# Create encoding pipelines
h264_deep = PipelineEntity(client, 'h264', 'interpipesrc name=h264_src format=time listen-to=deep \
! nvvideoconvert ! nvv4l2h264enc name=encoder maxperf-enable=1 insert-sps-pps=1 \
insert-vui=1 bitrate=10000000 preset-level=1 iframeinterval=30 control-rate=1 idrinterval=30 \
! h264parse ! interpipesink name=h264_sink async=true sync=false forward-eos=true forward-events=true')
pipelines_video_enc.append(h264_deep)

h265 = PipelineEntity(client, 'h265', 'interpipesrc name=h265_src format=time listen-to=deep \
! nvvideoconvert ! nvv4l2h265enc name=encoder maxperf-enable=1 insert-sps-pps=1 \
insert-vui=1 bitrate=10000000 preset-level=1 iframeinterval=30 control-rate=1 idrinterval=30 \
! h265parse ! interpipesink name=h265_sink async=true sync=false forward-eos=true forward-events=true')
pipelines_video_enc.append(h265)

jpeg = PipelineEntity(client, 'jpeg', 'interpipesrc name=jpeg_src format=time listen-to=deep \
! nvvideoconvert ! video/x-raw(memory:NVMM),format=NV12,width=1920,height=1080 ! nvjpegenc ! \
interpipesink name=jpeg forward-events=true forward-eos=true sync=false async=false \
enable-last-sample=false drop=true')
pipelines_snap.append(jpeg)

# Create recording pipelines
record_h264 = PipelineEntity(client, 'record_h264', 'interpipesrc format=time \
allow-renegotiation=false listen-to=h264_sink ! h264parse ! matroskamux ! filesink \
name=filesink_record_h264 location=test-h264.mkv')
pipelines_video_rec.append(record_h264)

record_h265 = PipelineEntity(client, 'record_h265', 'interpipesrc format=time \
allow-renegotiation=false listen-to=h265_sink ! h265parse ! matroskamux ! filesink \
name=filesink_record_h265 location=test-h265.mkv')
pipelines_video_rec.append(record_h265)

# Create snapshot pipeline
snapshot = PipelineEntity(client, 'snapshot', 'interpipesrc format=time listen-to=jpeg \
num-buffers=1 ! filesink name=filesink_snapshot location=test-snapshot.jpg')
pipelines_snap.append(snapshot)

# Play base pipelines
for pipeline in pipelines_base:
    pipeline.play()

time.sleep(10)

# Menu for the users

def main():
    while (True):
        print("\nMedia Server Menu\n \
             1) Start recording\n \
             2) Take a snapshot\n \
             3) Stop recording\n \
             4) Exit")

        option = int(input('\nPlease select an option:\n'))

        if option == 1:
            rec_name = str(input("Enter the name of the video recording (without extension):\n"))
            #Set locations for video recordings
            for pipeline in pipelines_video_rec:
                pipeline.set_file_location(rec_name + '_' + pipeline._name + '.mkv')

            #Play video recording pipelines
            for pipeline in pipelines_video_rec:
                pipeline.play()

            #Play video encoding pipelines
            for pipeline in pipelines_video_enc:
                pipeline.play()

            time.sleep(20)
    
        elif option == 2:
            snap_name = str(input("Enter the name of the snapshot (without extension):\n"))

            #Set location for snapshot
            snapshot.set_file_location(snap_name + '_' + snapshot._name + '.jpeg')

            #Play snapshot pipelines
            for pipeline in pipelines_snap:
                pipeline.play()

            time.sleep(5)

        elif option == 3:
            #Send EOS event to encode pipelines for proper closing
            #EOS to recording pipelines
            for pipeline in pipelines_video_enc:
                pipeline.eos()
            #Stop recordings
            for pipeline in pipelines_video_rec:
                pipeline.stop()
            for pipeline in pipelines_video_enc:
                pipeline.stop()

        elif option == 4:
            # Send EOS event to encode pipelines for proper closing
            # EOS to recording pipelines
            for pipeline in pipelines_video_enc:
                pipeline.eos()
            # Stop pipelines
            for pipeline in pipelines_snap:
                pipeline.stop()
            for pipeline in pipelines_video_rec:
                pipeline.stop()
            for pipeline in pipelines_video_enc:
                pipeline.stop()
            for pipeline in pipelines_base:
                pipeline.stop()

            # Delete pipelines
            for pipeline in pipelines_snap:
                pipeline.delete()
            for pipeline in pipelines_video_rec:
                pipeline.delete()
            for pipeline in pipelines_video_enc:
                pipeline.delete()
            for pipeline in pipelines_base:
                pipeline.delete()
            break
    
        else:
    	    print('Invalid option')

main()

