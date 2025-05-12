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
import uuid
import asyncio
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
import nodes
import glob

import folder_paths

base_path = os.path.dirname(os.path.realpath(__file__))
models_dir = os.path.join(base_path, "models")
user_dir = os.path.join(base_path, "user")
routes = PromptServer.instance.routes
_polltimer_registration_in_progress = False
_registerAndSetInfo_registration_in_progress = False
gadzoinks_url = "https://e6h2r5adh8.execute-api.us-east-1.amazonaws.com/prod/"

class GlobalState:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            if cls._instance is None:
                cls._instance = super(GlobalState, cls).__new__(cls)
                cls._instance.initialize()
        return cls._instance

    def initialize(self):
        self.handle = ""
        self.authkey = ""
        self.qservermode = False
        self.enableAPI = False
        self.serverName = ""
        self.api_handle = None
        self.api_authkey = None
        self.prompt_id = ""
        self.qserverid = None
        self.machineID = None
        self.job={}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            dprint(f"GlobalState cls._instance is None")
            cls()
        return cls._instance
    
    @classmethod
    def dump(cls):
        instance = cls.get_instance()
        attrs = [
            'handle', 'authkey', 'qservermode', 'enableAPI', 
            'serverName', 'api_handle', 'api_authkey', 
            'prompt_id', 'qserverid', 'machineID'   ]
        max_length = max(len(attr) for attr in attrs)
        for attr in attrs:
            value = getattr(instance, attr)
            dprint(f"{attr:<{max_length}} : {value}")



def dprint(*args, sep=' ', end='\n', file=sys.stdout, flush=True):
    #print(*args, sep=sep, end=end, file=file, flush=flush)
    #logger.info(sep.join(map(str, args)))
    pass


class SaveImageGadzoinks:
    instance = None
    def __init__(self):
        global_state = GlobalState.get_instance()
        self.instance = self
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"
        self.prefix_append = "gz"
        self.compress_level = 7 # png is lossless, 7 is high compression
        routes = PromptServer.instance.routes
        self.routes = routes
        self.handle = global_state.handle
        self.authkey = global_state.authkey
        self.set_timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        self.set_name = None
        dprint("__init__" ,flush=True)
        
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                 "upload_image":  ("BOOLEAN", {"default": True}),
                 "private_storage":  ("BOOLEAN", {"default": False}),
                 "age": (["17",  "12", "4" ],),
                 "set_name": ("STRING",{"default":""}),
                "images": ("IMAGE", {})
            },
            "optional":{
                "dynprompt": ("DYNPROMPT", {})
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO"
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "save_images_gadzoinks"
    OUTPUT_NODE = True
    CATEGORY = "Gadzoinks"
    JAVASCRIPT = "gadzoinks.js"

    def save_images_gadzoinks(self,upload_image , private_storage, age,set_name, images ,dynprompt=None,unique_id=None, prompt=None, extra_pnginfo=None):
        global_state = GlobalState.get_instance()
        self.handle = global_state.handle
        self.authkey = global_state.authkey
        dprint(f"save_images_gadzoinks unique_id={unique_id}")
        dprint(f"save_images_gadzoinks dynprompt={dynprompt}")
        dprint(f"save_images_gadzoinks prompt={prompt}")
        dprint(f"save_images_gadzoinks extra_pnginfo={extra_pnginfo}")
        if not upload_image:
            dprint(f"save_images_gadzoinks not upload_image")
            return { "ui": { "images": list() } }
        
        #promptRC = PromptServer.instance.send_sync("gadzoinks-gadzoinks-current-prompt-id", {})
        #dprint(f"save_images_gadzoinks: promptRC:{promptRC} prompt_id:{global_state.prompt_id}")
    
        computed_prompt = None
        if dynprompt is not None:
            try:
                from comfy_execution.graph import DynamicPrompt
                # Check if dynprompt is a DynamicPrompt instance
                if isinstance(dynprompt, DynamicPrompt):
                    dprint("Found valid DynamicPrompt instance QAQ")
                    # Search for GPromptsData nodes in the dynamic prompt
                    dprint(f"dynprompt.all_node_ids: {dynprompt.all_node_ids() }")
                    for node_id in dynprompt.all_node_ids():
                        node = dynprompt.get_node(node_id)
                        dprint(f"node {node_id} : {node}")
                        # Look for our specific metadata nodes from GPrompts
                        if "class_type" in node and node["class_type"] == "GPromptsData":
                            if "data" in node:
                                prompt_metadata = node["data"]
                                dprint(f"Found gprompts metadata 1: {prompt_metadata} QAQ")
                                # Add to our metadata
                                computed_prompt = prompt_metadata.get("computed_prompt")
                                dprint(f"computed_prompt:{computed_prompt}")
                                break
                else:
                    # If dynprompt is not a DynamicPrompt instance but contains data
                    dprint(f"dynprompt is not a DynamicPrompt instance: {type(dynprompt)} QAQ")
                    dprint(f"dynprompt 2:{dynprompt}")
                    if hasattr(dynprompt, 'original_prompt'):
                        # It might be the original prompt object
                        metadata["original_prompt"] = dynprompt.original_prompt
            except Exception as e:
                dprint(f"Error processing dynprompt: {str(e)}")



        if computed_prompt:
            dprint(f"Have computed_prompt:{computed_prompt} QAQ")

        isNewSet = False
        if set_name:
            if set_name != self.set_name:
                self.set_name = set_name
                self.set_timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
                isNewSet = True
                dprint("NEW SET")
        handle = global_state.handle
        authkey = global_state.authkey
        dprint(f"save_images_gadzoinks: handle: {self.handle}, authkey: {self.authkey}, set_name:{set_name} self.set_timestamp:{self.set_timestamp} isNewSet:{isNewSet}", flush=True)
        dprint(f"save_images_gadzoinks: global_state.api_handle: {global_state.api_handle}, global_state.api_authkey: {global_state.api_authkey}" )
        handle = global_state.api_handle if global_state.api_handle is not None else global_state.handle
        authkey = global_state.api_authkey if global_state.api_authkey is not None else global_state.authkey
        userToken = None
        uuid = None
        n = prompt.get(f"{unique_id}")   # this is the gadzoinks node
        # check if we are uploading an image from an external job , in which case we use userToken not handle/auth
        if n:
            uuid = n.get("uuid")  # only jobs have a uuid in the node
            if uuid:
                dprint(f"save_images_gadzoinks: uuid:{uuid}")
                job = global_state.job.get(uuid)
                if job:
                    dprint(f"save_images_gadzoinks: job:{job}")
                    handle = job.get("handle",handle)
                    authkey = job.get("authkey",authkey)
                    userToken = job.get('userToken')
            else:
                dprint(f"save_images_gadzoinks: using handle/auth")
                # this is BAD code, we ask front end for handle/authkey, and wait for global_state to get updated
                if not handle or not authkey:
                    PromptServer.instance.send_sync("gadzoinks-get-auth",{})
                    time.sleep(0.20) # prompt server is async, which will call python async
                    handle = global_state.handle
                    authkey = global_state.authkey
                    if not handle or not authkey:
                        PromptServer.instance.send_sync("gadzoinks-get-auth",{})
                        time.sleep(0.80) # prompt server is async, which will call python async
                        handle = global_state.handle
                        authkey = global_state.authkey
                    dprint(f"save_images_gadzoinks: queried front end for auth. {handle} {authkey}")
                    if not handle or not authkey:
                        PromptServer.instance.send_sync("gadzoinks-show-alert",{"message":"Handle / Authkey not set, check settings."})
                        return {}
        dprint(f"save_images_gadzoinks: USING handle: {handle}, authkey: {authkey} userToken:{userToken}")
        filename_prefix = ""
        prompt_info = ""
        metadata = None
        if prompt is not None:
            if unique_id in prompt:
                meta = prompt[unique_id].setdefault("_meta", {})
                if computed_prompt:
                    meta["computed_prompt"] = computed_prompt
                if uuid:
                    meta["uuid"] = uuid
                prompt[unique_id]["_meta"] = meta
            prompt_info = json.dumps(prompt)
        if not args.disable_metadata:
            metadata = {"prompt": prompt_info}
            if extra_pnginfo is not None:
                for x in extra_pnginfo:
                    metadata[x] = json.dumps(extra_pnginfo[x])
            
        dprint(f"metadata for write {metadata}")
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, self.output_dir, images[0].shape[1], images[0].shape[0])
        filename = f"gz_{filename}"
        results = list()
        dprint(f"save_images_gadzoinks 30")
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
            thumb_file = f"thumb_{file}"
            dprint(f"save_images_gadzoinks file:{file} thumb_file:{thumb_file}")
            img.save(os.path.join(full_output_folder, file), 
                     pnginfo=metadata, compress_level=self.compress_level)
            img.thumbnail((160, 160))  # Resize in-place
            img.save(os.path.join(full_output_folder, thumb_file), pnginfo=metadata,
                     compress_level=self.compress_level)
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
                "set_timestring" : self.set_timestamp,
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
                "extra" : extra,
                "include_thumb" : 1
            }
            if computed_prompt:
                form_data["computed_prompt"] = computed_prompt
            if userToken:
                form_data["userToken"] = userToken
            else:
                form_data["handle"] =  handle
                form_data["authkey"] = authkey
            if set_name:
                form_data["set_name"] = set_name
                if isNewSet:
                    form_data["start_of_set"] = 1
            dprint(f"save_images_gadzoinks form:{form_data}")
            jd = json.dumps(form_data)
            url = gadzoinks_url+"webupload"    
            dprint(url)
            resp = requests.post(url, json=form_data)
            dprint(f"webupload response:{resp}")
            msg = None
            if resp.status_code > 299:
                msg = "webupload failed"
            else:
                j = resp.json()
                dprint(f"resp.json:{j}")
                status = j.get("status",500)
                if status == 200:
                    # upload image via presigned URL, using url and fields 
                    url = j["url"]
                    fields = j["fields"]
                    files = {'file':open(os.path.join(full_output_folder, file),"rb") }
                    http_response = requests.post(url, data=fields , files=files )
                    dprint(f"S3 presigned upload image http_response:{http_response}")
                    # upload thumb
                    http_response = requests.post( j["thumb_url"], data = j["thumb_fields"],
                            files={'file':open(os.path.join(full_output_folder, thumb_file),"rb")})
                    dprint(f"S3 presigned upload thumb http_response:{http_response}")
                elif status == 400:
                    msg = "Error , Check handle/authkey in settings"
                    dprint(f"save_images_gadzoinks Gadzoinks Extension upload failed.  {msg}")
                elif status == 401:
                    msg = "Error , Check handle/authkey in settings"
                    dprint(f"save_images_gadzoinks Gadzoinks Extension upload failed.  {msg}")
                elif status == 403:
                    msg = j.get("message","unknown error uploading file")
                    dprint(f"save_images_gadzoinks Gadzoinks Extension upload failed.  {msg}")
                else:
                    msg = j.get("message","Something went wrong [SQUID]")
                    dprint(f"save_images_gadzoinks Gadzoinks Extension upload failed.  {msg}")
            # UI shows image, how to remove that, then can delete
            #os.remove(os.path.join(full_output_folder, file))
            if msg:
                PromptServer.instance.send_sync("gadzoinks-show-alert",{"message":msg})
            counter += 1
        return { "ui": { "images": results } }
    
    def IS_CHANGED(*args, **kwargs):
        return time.time()
    
    """
    # I think this is unused
    @PromptServer.instance.routes.post("/gadzoinks/settings")
    async def gadzoinks_settings(request):
        dprint("PromptServer.instance.routes.post(/gadzoinks/settings)")
        json_data = await request.json()
        PromptServer.instance.Comfy_gadzoinks_handle = json_data.get('handle')
        PromptServer.instance.Comfy_gadzoinks_authkey = json_data.get('authkey')
        
        return web.Response(text="Settings updated")
    """
    
    @PromptServer.instance.routes.get("/gadzoinks/setting")
    async def setting(request):
        # I'm putting machneID here since this is called pretty early on
        global_state = GlobalState().get_instance()
        if not global_state.machineID:
            node = uuid.getnode()
            mac = ':'.join(['{:02x}'.format((node >> elements) & 0xff) for elements in range(0,8*6,8)][::-1])
            global_state.machineID = mac
        
        dprint(f"setting {request.rel_url.query}")
        params = request.rel_url.query
        global_state.handle = params.get('handle',global_state.handle)
        global_state.authkey = params.get('authkey',global_state.authkey)
        if global_state.serverName != params.get('serverName',global_state.serverName):
            global_state.qserverid = None
        global_state.serverName = params.get('serverName',global_state.serverName)
        v = params.get('enableAPI')
        if v:
            global_state.enableAPI =  ( "true" == v.lower())
        v = params.get('qservermode')
        if v:
            global_state.qservermode =  ( "true" == v.lower())
    
        dprint(f"setting: {global_state.handle}, {global_state.authkey} serverName:{global_state.serverName} enableAPI:{global_state.enableAPI} qservermode:{global_state.qservermode} machineID={global_state.machineID}", flush=True)
        return web.Response(text=f"Parameters received {params}")
    
    # This code duplicates whats used in server.py, but intercepting was problematic
    @PromptServer.instance.routes.get("/gadzoinks/models")
    async def gadzoinks_model_types(request):
        loadSettingsFromConfigFile()
        global_state = GlobalState.get_instance()
        if not global_state.enableAPI:
            return web.json_response( {"status":403, "message" : "Not enabled"})
        model_types = list(folder_paths.folder_names_and_paths.keys())
        return web.json_response(model_types)
        
    @PromptServer.instance.routes.get("/gadzoinks/models/{folder}")  
    async def gadzoinks_models(request):
        loadSettingsFromConfigFile()
        global_state = GlobalState.get_instance()
        if not global_state.enableAPI:
            return web.json_response( {"status":403, "message" : "Not enabled"})
        folder = request.match_info.get("folder", None)
        if not folder in folder_paths.folder_names_and_paths:
            return web.Response(status=404)
        files = folder_paths.get_filename_list(folder)
        files = [file for file in files if not file.startswith('private')]
        return web.json_response(files)
    
    @PromptServer.instance.routes.get("/gadzoinks/listLoras")
    async def listLoras(request):
        global_state = GlobalState.get_instance()
        if not global_state.enableAPI:
            return web.json_response( {"status":403, "message" : "Not enabled"})
        loras = list_files(os.path.join(base_path, "../../models/loras"))
        result = {"lora": loras  }
        json_result = json.dumps(result, indent=2)
        dprint(f"jr:{json_result}")
        return web.json_response(result)
    
    @PromptServer.instance.routes.get("/gadzoinks/listModels")
    async def listModels(request):
        global_state = GlobalState.get_instance()
        if not global_state.enableAPI:
            return web.json_response( {"status":403, "message" : "Not enabled"})
        unet = list_files(os.path.join(base_path, "../../models/unet"))
        checkpoints = list_files(os.path.join(base_path, "../../models/checkpoints"))
        result = {"unet": unet , "checkpoint" : checkpoints }
        json_result = json.dumps(result, indent=2)
        dprint(f"jr:{json_result}")
        return web.json_response(result)
    
    @PromptServer.instance.routes.post("/gadzoinks/prompt")
    async def gadzoinks_promptflow(req):
        loadSettingsFromConfigFile()
        global_state = GlobalState.get_instance()
        if not global_state.enableAPI:
            return web.json_response( {"status":403, "message" : "Not enabled","errcode":1})
        dprint(f"/gadzoinks/prompt ENTRY")
        global_state = GlobalState.get_instance()
        post = await req.post()
        body = await req.json()
        global_state.api_handle = body.get("handle")
        global_state.api_authkey = body.get("authkey")
        workflow_type = body.get("workflow_type")
        prompt = body.get("prompt")
        dprint(f"gadzoinks_promptflow prompt:{prompt}")
        if not prompt:
            return web.json_response( {"status":403, "message" : "Bad Input","errcode":2})
        # {'prompt_id': 'ef427448-d79a-4c18-84e9-9c98366b3176', 'number': 5, 'node_errors': {}}
        rc = await queue_prompt(prompt)
        job = { "handle" :  body.get("handle") , "authkey" : body.get("authkey") }
        uuid = body.get("uuid")
        global_state.job[uuid] = job  
        dprint(f"gadzoinks_promptflow  handle:{global_state.api_handle} authkey:{global_state.api_authkey} workflow_type:{workflow_type} prompt:{prompt}")
        dprint(f"gadzoinks_promptflow  queue_prompt RC:{rc}")
        result = {}
        if rc:
            result = {"prompt_id":rc["prompt_id"],"node_errors":rc["node_errors"],"status":200,"errcode":0}
        else:
            result = {"status":400, "message" : "Failed. Usually this means the server is missing a node that is in the workflow","errcode":3 }
        # is this needed, sets web workflow - does it work?
        # PromptServer.instance.send_sync("gadzoinks-gadzoinks-workflow", body)
        return web.json_response(result)
    
    @PromptServer.instance.routes.post("/gadzoinks/workflow")
    async def gadzoinks_workflow(req):
        post = await req.post()
        body = await req.json()
        handle = body.get("handle")
        authkey = body.get("authkey")
        workflow_type = body.get("workflow_type")
        workflow = body.get("workflow")
        rc = await queue_prompt(workflow)
        dprint(f"handle:{handle} authkey:{authkey} workflow_type:{workflow_type} workflow:{workflow}")
        result = {"job":"007"}
        PromptServer.instance.send_sync("gadzoinks-gadzoinks-workflow", body)
        return web.json_response(result)
    
    @PromptServer.instance.routes.get("/gadzoinks/polltimer")
    async def gadzoinks_polltimer(req):
        loadSettingsFromConfigFile()
        try:
            global _polltimer_registration_in_progress
            global_state = GlobalState.get_instance()
            if not global_state.qservermode:
                dprint(f"gadzoinks_polltimer EXIT qservermode not enabled")
                return web.json_response({})
            qa = PromptServer.instance.prompt_queue.get_current_queue()
            if qa != ([], []):
                dprint(f"gadzoinks_polltimer EXIT get_current_queue():{qa}")
                _polltimer_registration_in_progress = False
                return web.json_response({})
            
            dprint(f"gadzoinks_polltimer _polltimer_registration_in_progress:{_polltimer_registration_in_progress}",flush=True)  
            if _polltimer_registration_in_progress:
                return
            _polltimer_registration_in_progress = True
            if global_state.qserverid is None:
                dprint(f"gadzoinks_polltimer  handle:{global_state.handle} qid:{global_state.qserverid}")
                if not global_state.handle:
                    dprint(f"gadzoinks_polltimer A")
                    PromptServer.instance.send_sync("gadzoinks-push-settings",{})
                    return web.json_response({})
                try:
                    asyncio.create_task(registerAndSetInfo())
                except Exception as e:
                    dprint(f"Error in gadzoinks_polltimer registerAndSetInfo: {str(e)}",flush=True)
            else:
                try:
                    asyncio.create_task(poppromptflow())
                except Exception as e:
                    dprint(f"Error in gadzoinks_polltimer poppromptflow: {str(e)}",flush=True)
            return web.json_response({})
        finally:
            _polltimer_registration_in_progress = False
    

    @routes.post("/gadzoinks/current_prompt_id")
    async def gadzoinks_current_prompt_id(req):
        loadSettingsFromConfigFile()
        global_state = GlobalState.get_instance()
        post = await req.post()
        global_state.prompt_id = post.get("prompt_id")
        dprint(f"gadzoinks_current_prompt_id prompt_id:{global_state.prompt_id}")
        
    @routes.post("/gadzoinks_link")
    async def gadzoinks_link(req):
        loadSettingsFromConfigFile()
        post = await req.post()
        handle = post.get("handle")
        authkey = post.get("authkey")
        dprint(f"handle:{handle} authkey:{authkey}")
        the_rest_url =  gadzoinks_url   
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
            message = j.get('message','')+'.\nIn the App, select an image and press 🔗 .'
            dprint(f"oops {j.get('message')}")
        else:
            message = "problem. Check your username and authkey in Settings ⚙️  / Gadzoinks"
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
'''

'''
async def poppromptflow():
    global _registerAndSetInfo_registration_in_progress
    if _registerAndSetInfo_registration_in_progress:
        dprint(f"_registerAndSetInfo_registration_in_progress")
        return
    dprint(f"poppromptflow ENTRY")
    global_state = GlobalState.get_instance()
    if not global_state.handle:
        dprint(f"poppromptflow handle:{global_state.handle}")
        PromptServer.instance.send_sync("gadzoinks-push-settings",{})
        return
    url = gadzoinks_url + "qserver/popprompflow"
    try:
        async with aiohttp.ClientSession() as session:
            pl = {"handle": global_state.handle, "authtoken": global_state.authkey, "name" : "TBD",
                            "machineID" : global_state.machineID,"serverID" :global_state.qserverid}
            async with session.post(url, json=pl) as resp:
                response_data = await resp.json()
                status = response_data.get('status')
                message = response_data.get('message')
                haveJob = response_data.get('haveJob')
                message = response_data.get('message')
                uuid = response_data.get('uuid')
                userToken = response_data.get('userToken')
                startUrl = response_data.get('startUrl')
                endUrl = response_data.get('endUrl')
                dprint(f"poppromptflow status:{status} haveJob:{haveJob} message:{message}")
                if haveJob > 0:
                    pf = response_data.get('promptFlow')
                    global_state.startUrl = startUrl
                    global_state.endUrl = endUrl
                    dprint(f"promptFlow:{pf}")
                    rc = await queue_prompt(pf)  # Add to Comfyui Queue
                    # check if rc.node_errors is not {}
                    #TODO handle / auth. replaced with upload_token
                    if rc:
                        job = { "userToken" : userToken, "uuid" : uuid,
                          "startUrl" : startUrl , "endUrl" : endUrl, "prompt_id" : rc.get("prompt_id")
                           , "number" : rc.get("number")}
                    else:
                        #TODO
                        dprint(f"rc = await queue_prompt() failed")
                    global_state.job[uuid] = job  
                    dprint(f"poppromptflow  job:{job} rc:{rc}")
    except Exception as e:
        dprint(f"poppromptflow {e}")
        raise
'''

'''
async def registerAndSetInfo():
    global _registerAndSetInfo_registration_in_progress
    if _registerAndSetInfo_registration_in_progress:
        return
    _registerAndSetInfo_registration_in_progress = True
    dprint(f"registerAndSetInfo ENTRY")
    global_state = GlobalState.get_instance()
    url = gadzoinks_url + "qserver/createserverid"
    try:
        if not global_state.handle:
            dprint(f"registerAndSetInfo handle:{global_state.handle}")
            PromptServer.instance.send_sync("gadzoinks-push-settings",{})
            return
        async with aiohttp.ClientSession() as session:
            sname = global_state.serverName or  os.getenv('HOSTNAME') or os.getenv('COMPUTERNAME') or "NADA"
            pl = {"handle": global_state.handle, "authtoken": global_state.authkey, 
                            "machineID" : global_state.machineID,"name" : sname}
            async with session.post(url, json=pl) as resp:
                response_data = await resp.json()
                serverID = response_data.get('serverID')
                message = response_data.get('message')
                if serverID:
                    global_state.qserverid = serverID
                dprint(f"createserverid message:{message} serverID:{serverID} payload={pl}" ,flush=True)
                # Optionally store message or other response data in global_state
                # Next set info
                try:
                    url2 = gadzoinks_url + "qserver/setserverinfo"
                    name = sname
                    d = os.path.join(base_path, "../../models/unet")
                    unet = list_files(os.path.join(base_path, "../../models/unet"))
                    checkpoint = list_files(os.path.join(base_path, "../../models/checkpoints"))
                    lora = list_files(os.path.join(base_path, "../../models/loras"))

                    info = { "type" : 1 , "name" : name, "company" : "MeSoft", 
                            "instance_id" : global_state.machineID , 
                            "details" : f"I am {sname}" }
                    payload = { "handle": global_state.handle,
                               "authtoken": global_state.authkey, 
                               "serverID" : serverID , "unet" : unet ,
                               "checkpoint" : checkpoint , 
                               "lora": lora, "info" : info }
                    async with aiohttp.ClientSession() as session2:
                        async with session.post(url2, json=payload) as resp2:
                            response2_data = await resp2.json()
                            dprint(f"setserverinfo response2_data:{response2_data}" ,flush=True)
                except Exception as e:
                    dprint(f"setserverinfo {e}")
                    raise
                finally:
                    _registerAndSetInfo_registration_in_progress = False
    except Exception as e:
        dprint(f"createserverid {e}")
        _registerAndSetInfo_registration_in_progress = False
        raise
            
async def get_current_prompt_id():
    async with aiohttp.ClientSession() as session:
        async with session.get('http://localhost:8188/gadzoinks/current_prompt_id') as response:
            if response.status == 200:
                data = await response.json()
                return data['prompt_id']
            else:
                print(f"Error: {response.status}")
                return None

async def queue_prompt(prompt):
    url = "http://127.0.0.1:8188/prompt"
    payload = {"prompt": prompt}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            print(f"queue_prompt() An error occurred: {e}")
            return None
'''
def queue_prompt(prompt):
    url = "http://127.0.0.1:8188/prompt"
    payload = {"prompt": prompt}
    
    try:
        response = requests.post(url, json=payload)
        dprint(f"queue_prompt response:{response}")
        response.raise_for_status()  # Raises a HTTPError if the status is 4xx, 5xx
        return response.json()  # If you expect a JSON response
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None
'''

def get_path_depth(path):
    return len(os.path.abspath(path).rstrip(os.sep).split(os.sep))

def list_files(root_path):
    result = []
    try:
        root_depth = get_path_depth(root_path)
        root_path = os.path.normpath(root_path)
        dprint(f"list_files  root_path:{root_path}")
        # For Windows, we need to handle symlinks differently
        if os.name == 'nt':
            import win32file
            def is_symlink(path):
                try:
                    return bool(win32file.GetFileAttributes(path) & win32file.FILE_ATTRIBUTE_REPARSE_POINT)
                except:
                    return False
        else:
            def is_symlink(path):
                return os.path.islink(path)

        for dirpath, dirnames, filenames in os.walk(root_path,followlinks=True):
            dirpath = os.path.normpath(dirpath)
            current_depth = get_path_depth(dirpath)
            depth_difference = current_depth - root_depth
            dprint(f"dirpath:{dirpath} dirnames:{dirnames}, filenames:{filenames}")
            dprint(f"dirpath:{dirpath} current_depth:{current_depth} depth_difference:{depth_difference}")
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            for file in filenames:
                if file.startswith('.'):
                    continue

                filename, extension = os.path.splitext(file)
                full_path = os.path.join(dirpath, file)

                if not extension:
                    continue
                if extension.lower() in {".jpeg", ".jpg", ".txt", ".png", ".pt",".download",".zip"}:
                    continue
                if is_symlink(full_path) and not os.path.exists(os.path.realpath(full_path)):
                    continue
                if depth_difference == 0:
                    result.append(filename+extension)
                else:
                    relative_path = os.path.relpath(dirpath, root_path)
                    if relative_path.startswith('private'):
                        pass # skip
                    else:
                        result.append(os.path.normpath(os.path.join(relative_path, filename+extension)))
    except Exception as e:
        dprint(f"Exception {e}")
    return result

def loadSettingsFromConfigFile():
        """
        if the website interface is stale or doesn't exist try and read from config file
        """
        user_directory = folder_paths.user_directory
        dprint(f"user_directory:{user_directory}")
        
        global_state = GlobalState.get_instance()
        if not global_state.handle:
            try:
                settings_path = os.path.join(user_directory, "default", "comfy.settings.json")
                dprint(f"user_directory:{user_directory} settings_path:{settings_path}")
                with open(settings_path, 'r') as file:
                    comfySettings = json.load(file)
                    if comfySettings:
                        dprint(f"comfySettings; {comfySettings}")
                        global_state.authkey = comfySettings.get("Gadzoinks.authkey")
                        global_state.handle = comfySettings.get("Gadzoinks.handle")
                        global_state.enableAPI = comfySettings.get("Gadzoinks.enableapi")
                        global_state.qservermode = comfySettings.get("Gadzoinks.qservermode")
                        global_state.serverName = comfySettings.get("Gadzoinks.serverName")
                        
                        global_state.dump()
            except FileNotFoundError:
                dprint("Settings file not found at ../../user/default/comfy.settings.json")
            except json.JSONDecodeError:
                dprint("Error parsing settings file - invalid JSON")
                
def get_local_url():
    """Get the current ComfyUI server URL with the correct port"""
    # Try to get the port from the server configuration
    server_address = None
    
    try:
        # Check if we can access the server's site object
        if hasattr(PromptServer.instance, 'app') and hasattr(PromptServer.instance.app, '_state'):
            # The server might have the port information in its state
            for site in PromptServer.instance.app._state.sites:
                if hasattr(site, '_server'):
                    sockets = site._server.sockets
                    if sockets:
                        sock = sockets[0]
                        # Get the actual port from the socket
                        _, port = sock.getsockname()
                        return f"http://localhost:{port}"
    except Exception as e:
        print(f"Error getting dynamic port: {e}")
    
    # Fallback: check environment variables or command line args
    try:
        # Check if port is specified in an environment variable
        port = os.environ.get('COMFYUI_PORT')
        if port:
            return f"http://localhost:{port}"
    except:
        pass
    
    # Last resort: try to get the port from PromptServer if possible
    try:
        if hasattr(PromptServer.instance, 'port'):
            return f"http://localhost:{PromptServer.instance.port}"
    except:
        pass
    
    # Ultimate fallback: use default ComfyUI port
    return "http://localhost:8188"

def find_route_handler(routes, method, path_pattern):
    """
    I don't know where this code came from, and I'm not sure how to call a returned route - should delete so,eday
    Find the handler function for a specific route pattern.
    
    Args:
        routes: The routes object containing registered routes
        method (str): HTTP method ('GET', 'POST', etc.)
        path_pattern (str): URL path pattern to match
        
    Returns:
        handler function if found, None otherwise
    """
    method = method.upper()
    
    def match_pattern(route_path, search_path):
        route_segments = route_path.split('/')
        search_segments = search_path.split('/')
        
        if len(route_segments) != len(search_segments):
            return False
            
        for route_seg, search_seg in zip(route_segments, search_segments):
            is_route_param = route_seg.startswith('{') and route_seg.endswith('}')
            is_search_param = search_seg.startswith('{') and search_seg.endswith('}')
            
            if (is_route_param and is_search_param) or route_seg == search_seg:
                continue
            return False
        return True

    for route in routes._items:
        if route.method == method and match_pattern(route.path, path_pattern):
            return route.handler
    return None

