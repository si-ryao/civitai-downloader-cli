Although Stable Diffusion makes art seem like a science, the slightest change in the math, tools, and hardware used can significantly change the outcome of the same generation request.

### Here are just a few reasons why you may not be able to reproduce an image:
1. It was generated on a different generation of graphic card.
1. The xformers optimization was used (which leads to less determinism)
1. A different version of Stable Diffusion software was used (it's common to have trouble reproducing images from just a month ago)
1. Textual Inversions (embeddings) were used that you may not have installed or may have named differently

### What can I do about it?
Right now, nothing. We recommend instead of trying to replicate an image exactly, **consider an image a starting point for your own journey into what's possible.**