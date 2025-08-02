How you use the various types of assets available on the site depends on the tool that you're using to generate your images using Stable Diffusion. We've included instructions for a few of them here, but if your tool isn't here, we invite you to open a [Q&A Discussion Post](https://github.com/civitai/civitai/discussions/categories/q-a) providing directions so we can include it here.

## [AUTOMATIC1111](https://github.com/AUTOMATIC1111/stable-diffusion-webui)

### Fine-tuned Model Checkpoints (Dreambooth Models)
1. Download the custom model
1. Place the model inside the `models/Stable-diffusion` directory of your AUTOMATIC1111 Web UI instance
1. Refresh your model list or restart the Stable Diffusion Web UI
1. Select the custom model from the `Stable Diffusion checkpoint` input field
1. Use the trained keyword in a prompt (listed on the custom model's page)
1. Make awesome images!

### Textual Inversions
1. Download the textual inversion
1. Place the textual inversion inside the `embeddings` directory of your AUTOMATIC1111 Web UI instance
1. Use the trained keyword in a prompt (listed on the textual inversion's page)
1. Make awesome images!

### Aesthetic Gradients
0. Install the [Aesthetic Gradients extension](https://github.com/AUTOMATIC1111/stable-diffusion-webui-aesthetic-gradients)
1. Download the aesthetic gradient
1. Place the aesthetic graident inside the `aesthetic_embeddings` directory of your AUTOMATIC1111 Web UI instance
1. Restart the Stable Diffusion Web UI
1. Adjust the aesthetic gradient setting
1. Make awesome images!

### Hypernetwork
1. Download the hypernetwork
1. Place the hypernetwork inside the `models/hypernetworks` directory of your AUTOMATIC1111 Web UI instance
1. Restart the Stable Diffusion Web UI
1. Select the hypernetwork from the `Hypernetwork` input field in settings
1. Adjust the hypernetwork strength using the `Hypernetwork strength` range slider in settings
1. Make awesome images!

### LoRA
[Video Guide by Lykon](https://www.youtube.com/watch?v=-bMeyXOZwN0)
1. Download the LoRA
1. Place the file inside the `models/lora` folder
1. Click on the `show extra networks` button under the `Generate` button (purple icon)
1. Go to the `Lora` tab and refresh if needed
1. Click on the one you want to apply, it will be added in the prompt
1. **Make sure to adjust the weight**, by default it's `:1` which is usually to high

#### Old UI (Versions Prior to Jan 20th)
0. Ensure that you've installed the [Additional Networks extension](https://github.com/kohya-ss/sd-webui-additional-networks), you can do this from the extensions tab. After installing you will need to restart AUTOMATIC1111.
1. Download the LoRA
1. Place the file inside the `extensions/sd-webui-additional-networks/models/lora` folder
1. On the `txt2img` or `img2img` tab, dropdown the `Additional Networks` area at the bottom of the page
1. Check enable
1. Set `Model 1` to the LoRA model you downloaded
1. Set `Weight 1` to a `0.85` a good starting value and adjust as needed
1. Make awesome images!

**Note:** You can use a LoRA with any model, but usually they are trained on a specific model and will perform best on that model or a derivative of that model.

### LoCon

0. Ensure that you're utilizing the latest version of Automatic1111 or that you've installed the [LoCon Extension](https://github.com/KohakuBlueleaf/a1111-sd-webui-locon)
1. Download the LoCon
1. Place the file inside the `models/LyCORIS` folder
1. Click on the `show extra networks` button under the `Generate` button (purple icon)
1. Go to the `LyCORIS` tab and refresh if needed
1. Click on the one you want to apply, it will be added in the prompt
1. **Make sure to adjust the weight**, by default it's `:1` which is usually too high

### Wildcards

0. Ensure that you've installed the [Wildcard Extension](https://github.com/AUTOMATIC1111/stable-diffusion-webui-wildcards)
1. Download the Wildcards archive
1. Extract the archive into `extensions/stable-diffusion-webui-wildcards/wildcards`
1. Use one or many of the wildcard words in your prompt to trigger the word replacement on generation (ex. `__hair-style__`)

### Motion Module

0. Ensure that you've installed the [AnimateDiff Extension](https://github.com/continue-revolution/sd-webui-animatediff)
1. Download the Motion Module
1. Place the file inside the `extensions/sd-webui-animatediff/model/` folder

## [Cmdr2's Stable Diffusion UI v2](https://stable-diffusion-ui.github.io/)
> 🙏 *Thanks [JeLuF](https://github.com/JeLuF) for providing these directions*

### Fine-tuned Model Checkpoints (Dreambooth Models)
1. Download the custom model in Checkpoint format (.ckpt)
1. Place the model file inside the models\stable-diffusion directory of your installation directory (e.g. C:\stable-diffusion-ui\models\stable-diffusion)
1. Reload the web page to update the model list
1. Select the custom model from the Model list in the Image Settings section
1. Use the trained keyword in a prompt (listed on the custom model's page)

## [aiNodes](https://github.com/XmYx/ainodes-pyside/tree/main)
> 🙏 *Thanks [osi1880vr](https://github.com/osi1880vr) for providing these directions*
1. Open the model download widget, search for the models in the list from Civitai.
1. Select the model you want as well as the config yaml which has to be used by that model.
1. Wait until the progressbar shows 100%.
1. Go back to the sampler widget where you choose the model from the list of installed models and press the dream button to render your prompt with the downloaded model.

You can follow these directions to download checkpoints (ckpt, safetensors), hypernetworks, textual inversion or aesthetic gradients. (And soon VAEs). We also support V2 models, both V2 formats are welcome here.

**For all those steps you never leave the UI**, just click buttons and you stay in your flow of creating art, not getting distracted with having to deal with your OS to move files or anything like that. It is as convenient as possible for now.

We hope you have plenty of fun using our UI and the models which are provided to you by the nice people of Civitai.
