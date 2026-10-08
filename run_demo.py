from ipaddress import IPv4Address, AddressValueError
from pathlib import Path
import socket

import qrcode

from app import app


PROJECT_FOLDER = Path(__file__).resolve().parent
QR_FILE = PROJECT_FOLDER / "static" / "office-qr.png"
PORT = 5000


def get_laptop_address():
    """Ask for and validate the laptop's Wi-Fi IPv4 address."""
    while True:
        value = input(
            "\nEnter your laptop's Wi-Fi IPv4 address: "
        ).strip()

        try:
            address = IPv4Address(value)
        except AddressValueError:
            print("Enter a valid IPv4 address, such as 192.168.1.5.")
            continue

        if (
            address.is_loopback
            or address.is_unspecified
            or address.is_multicast
            or address.is_link_local
            or not address.is_private
        ):
            print("Use your local Wi-Fi address from ipconfig.")
            continue

        # Check that this address belongs to this computer.
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind((str(address), 0))
        except OSError:
            print(
                "That address is not available on this laptop. "
                "Check the Wi-Fi IPv4 address in ipconfig."
            )
            continue

        return str(address)


def main():
    print("\nQUEUE BUSTERS — LOCAL WI-FI DEMO")
    print("Connect your laptop and phone to the same Wi-Fi.")
    print("Keep this terminal running during the demonstration.")

    laptop_address = get_laptop_address()
    student_url = f"http://{laptop_address}:{PORT}/"

    QR_FILE.parent.mkdir(parents=True, exist_ok=True)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=12,
        border=4,
    )
    qr.add_data(student_url)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white",
    )
    image.save(str(QR_FILE))

    print(f"\nStudent page: {student_url}")
    print(f"Staff dashboard: {student_url}staff")
    print(f"QR image saved to: {QR_FILE}")
    print(
        "\nOpen static/office-qr.png in VS Code "
        "and scan it using your phone."
    )
    print("Press Ctrl+C to stop the demo.\n")

    # Disable the debugger when other devices can access the app.
    app.run(
        host=laptop_address,
        port=PORT,
        debug=False,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()