import { $el } from "../../scripts/ui.js";
import { api } from "../../scripts/api.js";
import { app } from "../../scripts/app.js";
import { getPngMetadata, getWebpMetadata, importA1111, getLatentMetadata } from "../../scripts/pnginfo.js";

const referenceButton = document.querySelector('#comfy-load-default-button');
const newButton = $el("button", {
    id: "gadzoinks-load-button",
    textContent: "🔗 Gadzoinks",
    onclick: async () => { gadzoinks_link(); }
    });
referenceButton.insertAdjacentElement('afterend', newButton);

function gadzoinksShowAlert(event) {
    alert(event.detail.message);
}
api.addEventListener("gadzoinks-show-alert",gadzoinksShowAlert);

function dprint(...args) {
  //console.log(...args);
}

// This is for debugging only , and is not used
const ext = {
    // Unique name for the extension
    name: "gadzoinks.extension",
    async addCustomNodeDefs(defs, app) {
        // Add custom node definitions
        // These definitions will be configured and registered automatically
        // defs is a lookup core nodes, add yours into this
        dprint("[logging]", "add custom node definitions", "current nodes:", Object.keys(defs));
        //defs["Gadzoinks"]
        dprint("[logging] Gadzoinks node:",defs["Gadzoinks"])
    },
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        // Run custom logic before a node definition is registered with the graph
        dprint("[logging]", "before register node: ", nodeType, nodeData);

        // This fires for every node definition so only log once
        //delete ext.beforeRegisterNodeDef;
    },
    async registerCustomNodes(app) {
        // Register any custom node implementations here allowing for more flexability than a custom node def
        dprint("[logging]", "register custom nodes");
    },
    nodeCreated(node, app) {
        // Fires every time a node is constructed
        // You can modify widgets/add handlers/etc here
        dprint("[logging]", "node created: ", node);

        // This fires for every node so only log once
        //delete ext.nodeCreated;
    }
}
//app.registerExtension(ext);

function printNameAttributes() {
  const allElements = document.getElementsByTagName("*");

  for (let i = 0; i < allElements.length; i++) {
    const element = allElements[i];
    const nameAttribute = element.getAttribute("id");

    if (nameAttribute) {
      dprint(`Element ${element.tagName} has name attribute: ${nameAttribute}`);
    }
  }
}

function getWidget(node, name) {
    dprint("getWidget",node,name);
    return node.widgets.find((w) => w.name === name);
}
function getNodeType( type  ) {
    dprint("getNodeType ENTRY",type   );
    for (const outerNode of app.graph.computeExecutionOrder(false)) {
        if (outerNode.type == type) {
            return outerNode;
        }
    }
    return null;
}

function getNodeTypeWidgetOptions( type , name ) {
    dprint("getNodeTypeWidgetOptions ENTRY",type , name  );
    for (const outerNode of app.graph.computeExecutionOrder(false)) {
        if (outerNode.type == type) {
            const widgets = outerNode.widgets;
            dprint("setNodeTypeWidget:",type,name,widgets)
            for ( const w of widgets) {
                if (w.name==name) {
                    return w.options;
                }
            }
        }
    }
    return null;
}

function getNodeTypeWidget( type , name ) {
    dprint("getNodeTypeWidget ENTRY",type , name  );
    for (const outerNode of app.graph.computeExecutionOrder(false)) {
        if (outerNode.type == type) {
            const widgets = outerNode.widgets;
            dprint("setNodeTypeWidget:",type,name,widgets)
            for ( const w of widgets) {
                if (w.name==name) { 
                    return w.value;
                }
            }
        }
    }
    return null;
}

function setNodeTypeWidget( type , name , value ) {
    dprint("setNodeTypeWidget ENTRY",type , name , value );
    for (const outerNode of app.graph.computeExecutionOrder(false)) {
        if (outerNode.type == type) {
            const widgets = outerNode.widgets;
            dprint("setNodeTypeWidget:",type,name,widgets)
            for ( const w of widgets) {
                if (w.name==name) {  
                    w.value = value;
                    dprint("setNodeTypeWidget SET",type , name , value );
                }
            }
        }
    }
} 

async function gadzoinks_link() {
    try {
        var handle = ""
        var authkey = ""
        for (const outerNode of app.graph.computeExecutionOrder(false)) {
            if (outerNode.type == "Gadzoinks") {
                const widgets = outerNode.widgets;
                dprint("widgets",widgets)
                for ( const w of widgets) {
                    if (w.name=="handle") { handle = w.value; }
                    if (w.name=="authkey") { authkey = w.value; }
                }
            }
        }
        dprint("got:",handle,authkey)
        if (handle.legth==0 || authkey.length == 0) {
            alert("Could not find handle and authkey. Make sure you have a Gadzoinks node added and credentials entered");
            return;
        }
        const body = new FormData();
        body.append('handle',handle);
        body.append('authkey', authkey);
        const rPromise =  api.fetchApi("/gadzoinks_link", { method: "POST", body, });
        const res = await rPromise;
        const data = await res.json();
        dprint( "res:",res );
        dprint( "data:",data );
        const prompt = data["A1111_prompt"];
        // const payload = data.get("payload",{} ); 
        const good = data.good;
        const message = data.message;
        if ( !good && message.length > 0 ) {
            alert(message);
            return
        }
        dprint( "prompt:",prompt );
        updateGraphInPlace(app.graph, prompt);
    } catch (error) {
        console.error(error);
    }
}

function updateGraphInPlace(graph,parameters) {
    function popOpt(name) {
            const v = opts[name];
            delete opts[name];
            return v;
    }
    const p = parameters.lastIndexOf("\nSteps:");    
    if (p <= -1) {
        return 1;
    }
    const opts = parameters
        .substr(p)
        .split("\n")[1]
        .match(new RegExp("\\s*([^:]+:\\s*([^\"\\{].*?|\".*?\"|\\{.*?\\}))\\s*(,|$)", "g"))
        .reduce((p, n) => {
                const s = n.split(":");
                if (s[1].endsWith(',')) {
                        s[1] = s[1].substr(0, s[1].length -1);
                }
                p[s[0].trim().toLowerCase()] = s[1].trim();
                return p;
        }, {});
    const p2 = parameters.lastIndexOf("\nNegative prompt:", p);
    if (p2 <= -1) {
        return 2;
    }
    let positive = parameters.substr(0, p2).trim();
    let negative = parameters.substring(p2 + 18, p).trim();
    const ceil64 = (v) => Math.ceil(v / 64) * 64;
    dprint("updateGraphInPlace:",positive,negative,opts)

    const ckptNode = LiteGraph.getNodeType("CheckpointLoaderSimple");
    const clipSkipNode = LiteGraph.getNodeType("CLIPSetLastLayer");
    const positiveNode = LiteGraph.getNodeType("CLIPTextEncode");
    const negativeNode = LiteGraph.getNodeType("CLIPTextEncode");
    const samplerNode = LiteGraph.getNodeType("KSampler");
    const imageNode = LiteGraph.getNodeType("EmptyLatentImage");
    const vaeNode = LiteGraph.getNodeType("VAEDecode");
    const vaeLoaderNode = LiteGraph.getNodeType("VAELoader");
    const saveNode = LiteGraph.getNodeType("SaveImage");
    let hrSteps = null;
    const handlers = {
        model(v) {
            // TODO notify user if model was not found, and nothing was updated
            if (!v.endsWith('.safetensors')) {
                v = `${v}.safetensors`;
            }
            const options = getNodeTypeWidgetOptions("CheckpointLoaderSimple","ckpt_name");
            dprint("ckpt_name opt",v,options);
            const o = options.values.find((w) => w == v);
            if (o) {
                dprint("ckpt_name FOUND IT");
                setNodeTypeWidget("CheckpointLoaderSimple","ckpt_name", v);
            }
        },
        "vae"(v) {
                //setWidgetValue(vaeLoaderNode, "vae_name", v, true);
        },
        "cfg scale"(v) {
            setNodeTypeWidget("KSampler","cfg", +v);
        },
        "clip skip"(v) {
            setNodeTypeWidget("CLIPSetLastLayer","stop_at_clip_layer", -v);
        },
        sampler(v) {
                let name = v.toLowerCase().replace("++", "pp").replaceAll(" ", "_");
                if (name.includes("karras")) {
                    name = name.replace("karras", "").replace(/_+$/, "");
                    setNodeTypeWidget("KSampler","scheduler", "karras");
                } else {
                    setNodeTypeWidget("KSampler","scheduler", "normal");
                }
                //const w = getWidget(samplerNode, "sampler_name");
                const w = getNodeTypeWidget("KSampler","sampler_name");
                dprint("sampler_name w:",w);
                const options = getNodeTypeWidgetOptions("KSampler","sampler_name");
                dprint("sampler_name options :",options);
                dprint("sampler_name options.values :",options.values);
                dprint("name",name);
                const o = options.values.find((w) => w === name || w === "sample_" + name);
                if (o) {
                    dprint("sampler_name FOUND IT");
                    setNodeTypeWidget("KSampler","sampler_name", o);
                }
        },
       size(v) {
                const wxh = v.split("x");
                const w = ceil64(+wxh[0]);
                const h = ceil64(+wxh[1]);
                const hrUp = popOpt("hires upscale");
                const hrSz = popOpt("hires resize");
                hrSteps = popOpt("hires steps");
                let hrMethod = popOpt("hires upscaler");
                //TODO hires
                setNodeTypeWidget("EmptyLatentImage", "width", w);
                setNodeTypeWidget("EmptyLatentImage","height", h); 
       },
       steps(v) {
                setNodeTypeWidget("KSampler","steps", +v);
        },
        seed(v) {
                setNodeTypeWidget("KSampler","seed", +v);
        },
    };
    for (const opt in opts) {
        dprint("look for opt",opt);
        if (opt in handlers) {
            dprint("found opt,processing",opt);
            handlers[opt](popOpt(opt));
        }
    }
    const ksampler = getNodeType("KSampler")
    dprint("ksampler",ksampler);
    dprint("ksampler",ksampler.serialize());
    const kpos = ksampler.getInputNode( 1 );   // why is 1 the positive node. I guess (model,pos,neg,latentImage)
    dprint("kpos",kpos);
    const kneg = ksampler.getInputNode( 2 );
    dprint("kneg",kneg);
    kpos.widget_values = [ positive ];
    kneg.widget_values = [ negative ];
    kpos.widgets[0].value = positive;
    kneg.widgets[0].value = negative;
    dprint("kpos",  ksampler.getInputNode( 1 ) );
    dprint("leftover opts",opts);
    return 0;
}


function replaceEmbeddings(text) {
    if(!embeddings.length) return text;
    return text.replaceAll(
            new RegExp(
                    "\\b(" + embeddings.map((e) => e.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\b|\\b") + ")\\b",
                    "ig"
            ),
            "embedding:$1"
    );
}

function setWidgetValue(node, name, value, isOptionPrefix) {
    dprint("setWidgetValue",node,name);
    const w = getWidget(node, name);
    if (isOptionPrefix) {
        const o = w.options.values.find((w) => w.startsWith(value));
        if (o) {
            w.value = o;
        } else {
            console.warn(`Unknown value '${value}' for widget '${name}'`, node);
            w.value = value;
        }
    } else {
        w.value = value;
    }
}

