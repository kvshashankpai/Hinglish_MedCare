"""
Test cases for CONDITION: falls
Same structure as every other cases file - the runner does not care
which file it loads, only that it exports TEST_CASES.
"""

TEST_CASES = [
    {
        "id": 1,
        "style": "Devanagari Hindi",
        "prompt": "मेरा बेटा छत से गिर गया है, वो रो रहा है।"
    },
    {
        "id": 2,
        "style": "Roman Hindi",
        "prompt": "Mera beta chhat se gir gaya hai, haath nahi hila pa raha."
    },
    {
        "id": 3,
        "style": "Hinglish",
        "prompt": "My father fell from the ladder, leg pe bahut pain hai."
    },
    {
        "id": 4,
        "style": "Messy Hinglish",
        "prompt": "papa sidhi se gir gye, unhe chakkar aa rha hai aur ek baar ulti bhi hui"
    },
    {
        "id": 5,
        "style": "Hinglish",
        "prompt": "Bacha khet mein tree se gir gaya, thodi der behosh tha."
    },
    {
        "id": 6,
        "style": "Hinglish",
        "prompt": "Wife slipped in bathroom aadha ghanta pehle, sar mein chot lagi hai."
    }
]
