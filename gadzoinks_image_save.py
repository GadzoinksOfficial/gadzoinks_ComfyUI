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

class GlobalState:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GlobalState, cls).__new__(cls)
            cls._instance.handle = ""
            cls._instance.authkey = ""
        return cls._instance
        

@PromptServer.instance.routes.get("/gadzoinks/setting")
async def custom_get_handler(request):
    dprint(f"custom_get_handler {request.rel_url.query}")
    params = request.rel_url.query
    global_state = GlobalState()
    global_state.handle = params.get('handle')
    global_state.authkey = params.get('authkey')
    dprint(f"custom_get_handler: {global_state.handle}, {global_state.authkey}", flush=True)
    return web.Response(text=f"Parameters received {params}")


#WEB_DIRECTORY = "./js"

def dprint(*args, sep=' ', end='\n', file=sys.stdout, flush=False):
    #print(*args, sep=sep, end=end, file=file, flush=flush)
    pass

class SaveImageGadzoinks:
    instance = None
    def __init__(self):
        global_state = GlobalState()
        self.instance = self
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"
        self.prefix_append = "gz"
        self.compress_level = 1
        routes = PromptServer.instance.routes
        self.routes = routes
        self.handle = global_state.handle
        self.authkey = global_state.authkey
        dprint("__init__" ,flush=True)
        
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                 "upload_image":  ("BOOLEAN", {"default": True}),
                 "private_storage":  ("BOOLEAN", {"default": False}),
                 "age": (["17",  "12", "4" ],),
                "images": ("IMAGE", {})
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO"
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "save_images_gadzoinks"
    OUTPUT_NODE = True
    CATEGORY = "Gadzoinks"
    JAVASCRIPT = "gadzoinks.js"

    def save_images_gadzoinks(self,upload_image , private_storage, age, images , prompt=None, extra_pnginfo=None):
        global_state = GlobalState()
        self.handle = global_state.handle
        self.authkey = global_state.authkey
        handle = global_state.handle
        authkey = global_state.authkey
        dprint(f"save_images_gadzoinks: handle: {self.handle}, authkey: {self.authkey}", flush=True)
        filename_prefix = ""
        prompt_info = ""
        if not upload_image:
            return 
        if prompt is not None:
            prompt_info = json.dumps(prompt)
        metadata = None
        if not args.disable_metadata:
            metadata = {"prompt": prompt_info}
            if extra_pnginfo is not None:
                for x in extra_pnginfo:
                    metadata[x] = json.dumps(extra_pnginfo[x])
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, self.output_dir, images[0].shape[1], images[0].shape[0])
        filename = f"gz_{filename}"
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
            try:
               age = age if age in {"4", "12", "17"} else "17"
            except:
                age = "17"
            vis = 0
            try:
                vis = int(private_storage)
            except:
                pass
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
                "maturityRating": age,
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

    @PromptServer.instance.routes.post("/gadzoinks/settings")
    async def gadzoinks_settings(request):
       json_data = await request.json()
       PromptServer.instance.Comfy_gadzoinks_handle = json_data.get('handle')
       PromptServer.instance.Comfy_gadzoinks_authkey = json_data.get('authkey')
       return web.Response(text="Settings updated")

    @routes.post("/gadzoinks_link")
    async def gadzoinks_link(req):
        post = await req.post()
        handle = post.get("handle")
        authkey = post.get("authkey")
        dprint(f"handle:{handle} authkey:{authkey}")
        the_rest_url =  "https://e6h2r5adh8.execute-api.us-east-1.amazonaws.com/prod/"
        headers = {'Accept': 'application/json', 'content-type':'application/json',
            'X-Gadzoink-handle':handle,  'X-Gadzoink-auth':authkey}
        resp = requests.post(the_rest_url + 'getparameters',json={"handle":handle, "authkey": authkey, "workflow" : {"workflow_type" : "comfyui"} }, headers=headers)
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
            print(f"problem getting image details")
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
        rcj = {"A1111_prompt":p,'good':good,'message':message,'payload':payload }
        if j.get('comfyui'):
            rcj['comfyui'] = j.get('comfyui')	
        return web.json_response(rcj)

