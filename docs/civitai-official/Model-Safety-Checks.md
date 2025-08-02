Since the Stable Diffusion community is currently using `.ckpt` files as their primary way of sharing models, which happens to be an inherently dangerous way to share things due to the possibility of dangerous code being embedded inside the pickled model files, it's important to ensure that the files being shared are scanned and verified as safe. This scanning is something that is currently performed by services like HuggingFace.

To keep things safe for Civitai users and other members of the community that have forked the service, [we've created a service](https://github.com/civitai/civitai/discussions/9) that can properly scan these files as well (also [open-source](https://github.com/civitai/model-scanner)). Files that have been verified as safe will receive an indicator on their Model page and a summary of their pickled contents, just like you'd see on HuggingFace. This feature was added on 11/11/2022. We suspect it will take roughly 24hrs to process the currently uploaded models.

**Verified Model on Civitai**

![Civitai Example](https://user-images.githubusercontent.com/607609/201232040-1d863540-c509-419a-8ff9-a273537c929c.png)



**Verified CKPT on HuggingFace**

![HuggingFace Verified Example](https://user-images.githubusercontent.com/607609/201218382-578cb8db-b796-4f32-8c29-1cf1bec748d0.png)
