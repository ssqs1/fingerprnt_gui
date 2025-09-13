import requests


api_url = "http://10.21.54.187"  # استبدل هذا بالرابط الصحيح للـ API


class Client:
   def register_user(self, email: str, name: str, images: list[bytes]):
        """
        Register a user with multiple fingerprint images (BMP format).

        Args:
            email (str): user email
            name (str): user name
            images (list[bytes]): list of BMP image bytes
        """
        # Prepare files list with correct field name 'files' and MIME type
        files = [
            ('files', (f'fingerprint_{i+1}.bmp', img, 'image/bmp'))
            for i, img in enumerate(images)
        ]

        data = {
            "email": email,
            "name": name
        }

        response = requests.post(
            f"{api_url}/auth/register-new-user",  # ✅ endpoint matches curl
            data=data,
            files=files,
            headers={"accept": "application/json"}
        )

        if response.status_code == 200:
            return response.json()
        else:
            print("Server error:", response.text)
            return None
   
   def check_fingerprint(self, image: bytes):

    files = {
        'file': ('fingerprint.bmp', image, 'image/bmp')  # ✅ نفس الفورم المطلوب
    }
    response = requests.post(
        f"{api_url}/auth/match-finger-print",
        files=files,
        headers={"accept": "application/json"}  # ✅ مثل الـ curl
    )
    if response.status_code == 200:
        return response.json()
    else:
      return None
