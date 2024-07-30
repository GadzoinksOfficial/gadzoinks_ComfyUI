import os
import sys
import json
import hashlib
import traceback
import math
import time
import random
import logging
import requests
from datetime import datetime
from PIL import Image, ImageOps, ImageSequence
from PIL.PngImagePlugin import PngInfo
import numpy as np
import safetensors.torch
from io import BytesIO
import struct
import comfy.utils
from comfy.cli_args import args
import folder_paths
import latent_preview
import node_helpers
from server import PromptServer
import aiohttp
from aiohttp import web
import traceback

routes = PromptServer.instance.routes

#WEB_DIRECTORY = "./js"

def dprint(*args, sep=' ', end='\n', file=sys.stdout, flush=False):
    pass

class SaveImageGadzoinks:
    instance = None
    def __init__(self):
        self.instance = self
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"
        self.prefix_append = ""
        self.compress_level = 4
        #routes = web.RouteTableDef()
        routes = PromptServer.instance.routes
        self.routes = routes
        self.hanlde = None
        self.authkey = None
    @classmethod
    def INPUT_TYPES(s):
        return { "required": 
            {"handle": ("STRING",{}),"authkey": ("STRING",{}), 
            "age": ("INT",{"default": 17, "min": 4, "max": 17}),
            "private": ("INT",{"default": 0, "min": 0, "max": 1, "step": 1}), 
            "images" : ("IMAGE", {}) },  
        "hidden": {"prompt":"PROMPT","extra_pnginfo":"EXTRA_PNGINFO"},}        

    RETURN_TYPES = ()
    FUNCTION = "save_images_gadzoinks"

    OUTPUT_NODE = True

    CATEGORY = "Gadzoinks"

    def save_images_gadzoinks(self, handle,authkey, age, private, images, prompt=None, extra_pnginfo=None):
        #dprint(f"testing")
        self.handle = handle
        self.authkey = authkey
        filename_prefix = ""
        # support save metadata for latent sharing
        prompt_info = ""
        if prompt is not None:
            prompt_info = json.dumps(prompt)
        metadata = None
        if not args.disable_metadata:
            metadata = {"prompt": prompt_info}
            if extra_pnginfo is not None:
                for x in extra_pnginfo:
                    metadata[x] = json.dumps(extra_pnginfo[x])
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, self.output_dir, images[0].shape[1], images[0].shape[0])
        filename = f".gz_{filename}"
        results = list()
        for (batch_number, image) in enumerate(images):
            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
            metadata = None
            if not args.disable_metadata:
                metadata = PngInfo()
                if prompt is not None:
                    metadata.add_text("prompt", json.dumps(prompt))
                if extra_pnginfo is not None:
                    for x in extra_pnginfo:
                        #dprint(f"extra_pnginfo: {json.dumps(extra_pnginfo[x])} ")
                        metadata.add_text(x, json.dumps(extra_pnginfo[x]))
            filename_with_batch_num = filename.replace("%batch_num%", str(batch_number))
            file = f"{filename_with_batch_num}_{counter:05}_.png"
            img.save(os.path.join(full_output_folder, file), pnginfo=metadata, compress_level=self.compress_level)
            results.append({
                "filename": file,
                "subfolder": subfolder,
                "type": self.type
            })
            fage = 17
            if age > 4 and age <=12 :
                fage = 12
            if age == 4:
                fage = 4
            vis = private
            extra = {}
            if prompt is not None:
                extra = json.dumps(prompt)
            form_data = {
                "handle": handle,
                "authkey": authkey,
                "keywords": "",
                "caption": "",
                "prompt": "",
                "nprompt": "",
                "maturityRating": str(fage),
                "ownerRanking": "0",
                "fileName": file,
                "fileType": "image/jpeg",
                "visibility" : vis,
                "app" : "comfyui",
                "extra" : extra
            }
            jd = json.dumps(form_data)
            url = "https://e6h2r5adh8.execute-api.us-east-1.amazonaws.com/prod/webupload"
            resp = requests.post(url, data=jd)
            #dprint(f"response:{resp}")
            j = resp.json()
            #dprint(f"resp.json:{j}")
            status = j.get("status",500)
            msg = None
            if status == 200:
                url = j["url"]
                #dprint(f"url {url}")
                fields = j["fields"]
                #dprint( f"fields {fields}" )
                #files = {'file': os.path.join(full_output_folder, file) }
                #files = {'file': open( (full_output_folder, file, 'image/jpeg')}
                #files = {'file': img. }
                files = {'file':open(os.path.join(full_output_folder, file),"rb") }
                #dprint(f"files:{files}")
                http_response = requests.post(url, data=fields , files=files )
                #dprint(f"http_response:{http_response}")
            elif status == 403:
                msg = j.get("message","unknown error uploading file")
                dprint(f"Gadzoinks Extension upload failed.  {msg}")
            # UI shows image, how to remove that, then can delete
            #os.remove(os.path.join(full_output_folder, file))
            if msg:
                PromptServer.instance.send_sync("gadzoinks-show-alert",{"message":msg})
            counter += 1
        return { "ui": { "images": results } }

    def IS_CHANGED(s, images):
        return time.time()


    @routes.post("/gadzoinks_link")
    async def gadzoinks_link(req):
        post = await req.post()
        handle = post.get("handle")
        authkey = post.get("authkey")
        dprint(f"{handle} {authkey}")
        the_rest_url =  "https://e6h2r5adh8.execute-api.us-east-1.amazonaws.com/prod/"
        headers = {'Accept': 'application/json', 'content-type':'application/json',
            'X-Gadzoink-handle':handle,  'X-Gadzoink-auth':authkey}
        resp = requests.post(the_rest_url + 'getparameters',json={}, headers=headers,data = {})
        j = resp.json()
        dprint(f" status:{resp.status_code} j:{j}")
        good = False
        message = ""
        payload = {}
        status = j.get("status",0)
        if status == 200:
            if "prompt" in j.get("payload",{}):
                good = True
            dprint("Good api call result")
        elif status == 204:
            message = j.get('message','')+'. Try linking again on the app.'
            dprint(f"oops {j.get('message')}")
        else:
            message = "problem"
            dprint(f"problem")
        p = ""
        if good:
            payload = j.get("payload")
            dprint(f"payload:{payload}")
            p = payload["prompt"]+"\nNegative prompt: "+payload.get("negative_prompt")+"\n"
            if "steps" in payload:
                p = p + f'Steps: {payload["steps"]},'
            if "sampler" in payload:
                p = p + f' Sampler: {payload["sampler"]},'
            if "cfg_scale" in payload:
                p = p + f' CFG scale: {payload["cfg_scale"]},'
            if "seed" in payload:
                p = p + f' Seed: {payload["seed"]},'
            if "width" in payload:
                p = p + f' Size: {payload["width"]}x{payload["height"]},'
            if "model" in payload:
                p = p + f' Model: {payload["model"]},'
            if p[-1] == ",":
                p = p[:-1]
            dprint(f"p:{p}")
        dprint(f"gadzoinks_link {req}")
        return web.json_response({"A1111_prompt":p,'good':good,'message':message,'payload':payload})

'''

routes = PromptServer.instance.routes
@routes.post('/image_chooser_message')
async def make_image_selection(request):
    post = await request.post()
    MessageHolder.addMessage(post.get("id"), post.get("message"))
    return web.json_response({})

class Cancelled(Exception):
    pass

class MessageHolder:
    stash = {}
    messages = {}
    cancelled = False
    
    @classmethod
    def addMessage(cls, id, message):
        if message=='__cancel__':
            cls.messages = {}
            cls.cancelled = True
        elif message=='__start__':
            cls.messages = {}
            cls.stash = {}
            cls.cancelled = False
        else:
            cls.messages[str(id)] = message
    
    @classmethod
    def waitForMessage(cls, id, period = 0.1, asList = False):
        sid = str(id)
        while not (sid in cls.messages) and not ("-1" in cls.messages):
            if cls.cancelled:
                cls.cancelled = False
                raise Cancelled()
            time.sleep(period)
        if cls.cancelled:
            cls.cancelled = False
            raise Cancelled()
        message = cls.messages.pop(str(id),None) or cls.messages.pop("-1")
        try:
            if asList:
                return [int(x.strip()) for x in message.split(",")]
            else:
                return int(message.strip())
        except ValueError:
            dprint(f"ERROR IN IMAGE_CHOOSER - failed to parse '${message}' as ${'comma separated list of ints' if asList else 'int'}")
            return [1] if asList else 1
'''

