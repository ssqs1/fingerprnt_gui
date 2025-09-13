class Device:
    def __init__(self):
        """
        initialize the device to read fingerprint
        
        """
    

    def read_fingerprint(self) -> bytes:
        """
        read the fingerprint from the device
        
        Returns:
            bytes: the fingerprint image in bytes
        """
    

    def save_fingerprint(self, img_bytes: bytes):
        """
        save the fingerprint image to a file
        
        Args:
            img_bytes (bytes): the fingerprint image in bytes
        """

    
    def send_images_to_server(self, img_bytes: bytes, server_url: str):
        """
        send the fingerprint image to the server
        
        Args:
            img_bytes (bytes): the fingerprint image in bytes
            server_url (str): the server URL to send the image to
        """