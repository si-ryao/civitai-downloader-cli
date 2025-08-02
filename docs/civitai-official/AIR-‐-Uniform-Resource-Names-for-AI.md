In response to challenges communicating what resource we intend for service providers and users to be using when testing out content, and in thinking ahead to how we believe AI Resources like those on Civitai, Hugging Face, and other platforms might be used, we propose a Uniform Resource Naming system, AIR (Artificial Intelligence Resource).

Here's the basic idea.

[About Uniform Resource Names](https://en.wikipedia.org/wiki/Uniform_Resource_Name)

## Spec
`urn:air:{ecosystem}:{type}:{source}:{id}@{version?}.?{format?}`
- `urn`: Uniform Resource Name *optional*
- `air`: Artificial Intelligence Resource *optional*
- `{ecosystem}`: Type of the ecosystem (`sd1`, `sd2`, `sdxl`)
- `{type}`: Type of the resource (`model`, `lora`, `embedding`, `hypernet`)
- `{source}`: Supported network source
- `{id}`: Id of the resource from the source
- `{format}`: The format of the model (`safetensor`, `ckpt`, `diffuser`, `tensor rt`) *optional*

## Examples
```
urn:air:sd1:model:civitai:2421@43533
urn:air:sd2:model:civitai:2421@43533
urn:air:sdxl:lora:civitai:328553@368189
urn:air:dalle:model:openai:dalle@2
urn:air:gpt:model:openai:gpt@4
urn:air:sdxl:model:huggingface:stabilityai/sdxl-vae
urn:air:sd1:model:leonardo:345435
```

## Parsing RegEx

**With Named Groups**
*Some regex systems do not support this*
```
^(?:urn:)?(?:air:)?(?:(?<ecosystem>[a-zA-Z0-9_\-\/]+):)?(?:(?<type>[a-zA-Z0-9_\-\/]+):)?(?<source>[a-zA-Z0-9_\-\/]+):(?<id>[a-zA-Z0-9_\-\/]+)(?:@(?<version>[a-zA-Z0-9_\-]+))?(?:\.(?<format>[a-zA-Z0-9_\-]+))?$
```

**Without Named Groups**
```
^(?:urn:)?(?:air:)?(?:([a-zA-Z0-9_\-\/]+):)?(?:([a-zA-Z0-9_\-\/]+):)?([a-zA-Z0-9_\-\/]+):([a-zA-Z0-9_\-\/]+)(?:@([a-zA-Z0-9_\-]+))?(?:\.([a-zA-Z0-9_\-]+))?$
```

