# instagram-archive-exif

a quick and dirty Python script that adds back EXIF tags (created/modified time, camera info, geolocation) to media exported from Instagram's data export tool.

## why?

the gods at Meta™®© decided to make life difficult for anyone _who dares_ take their rightfully-owned data anywhere else. god forbid you'd want to move things into a backup service for long-term storage? can't imagine why someone would do such a thing! 

well, apparently me. and I didn't want to manually tag thousands of media files with their date so my gallery app works. so I went the extra mile: all tags returned by instagram in separate JSON files are merge-able using this script. 

## instructions

TODO but:

```python
poetry install
# ... extract your archive into this folder ..
poetry run main.py [json files to process -- they're found at ./archive-name/content]
# follow the prompts and see the magic at /result once it's done
```

## special thanks
meta engineers, they can't be bothered to merge some EXIF tags into files at export time