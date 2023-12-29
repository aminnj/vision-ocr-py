#!/usr/bin/env python3

import sys
import os
import tempfile
import math

from typing import Literal, Union

import Quartz
from Foundation import NSURL, NSRange
import Vision

from Quartz.CoreGraphics import CGRectApplyAffineTransform, CGAffineTransformMakeScale


def _extract_text_from_image(img_path: str, origin: str, method: str) -> dict:
    output_entities = []

    def recognize_text_handler(request, error):
        observations = request.results()
        results = []
        for observation in observations:
            # Return the string of the top VNRecognizedText instance.
            recognized_text = observation.topCandidates_(1)[0]

            # Find the bounding-box observation for the string range.
            box_range = NSRange(0, len(recognized_text.string()))
            boxObservation, error = recognized_text.boundingBoxForRange_error_(
                box_range, None
            )

            # Get the normalized CGRect value.
            boundingBox = boxObservation.boundingBox()

            # Convert the rectangle from normalized coordinates to image coordinates.
            image_width = input_image.extent().size.width
            image_height = input_image.extent().size.height

            def denormalize_point(point):
                x, y = list(
                    Vision.VNImagePointForNormalizedPoint(
                        point, image_width, image_height
                    )
                )
                if origin == "top":
                    y = image_height - y
                return round(x, 3), round(y, 3)

            top_left = denormalize_point(boxObservation.topLeft())
            top_right = denormalize_point(boxObservation.topRight())
            bottom_left = denormalize_point(boxObservation.bottomLeft())
            bottom_right = denormalize_point(boxObservation.bottomRight())

            # Image coordinates start with (0,0) at the bottom left
            xmin = round(min(top_left[0], bottom_left[0]), 3)
            ymin = round(min(bottom_left[1], bottom_right[1]), 3)
            xmax = round(max(top_right[0], bottom_right[0]), 3)
            ymax = round(max(top_left[1], top_right[1]), 3)

            # To anchor (0,0) at top left (eg for matplotlib)
            if origin == "top":
                ymin, ymax = sorted([image_height - ymin, image_height - ymax])

            output_entities.append(
                dict(
                    text=recognized_text.string(),
                    confidence=round(recognized_text.confidence(), 3),
                    xmin=xmin,
                    ymin=ymin,
                    xmax=xmax,
                    ymax=ymax,
                    rotation_degrees=math.degrees(
                        math.atan2(
                            top_right[1] - top_left[1], top_right[0] - top_left[0]
                        )
                    ),
                    polygon=dict(
                        top_left=top_left,
                        top_right=top_right,
                        bottom_left=bottom_left,
                        bottom_right=bottom_right,
                    ),
                )
            )

    # Get the CIImage on which to perform requests.
    input_url = NSURL.fileURLWithPath_(img_path)
    input_image = Quartz.CIImage.imageWithContentsOfURL_(input_url)
    image_width = input_image.extent().size.width
    image_height = input_image.extent().size.height

    # Create a new image-request handler.
    request_handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(
        input_image, None
    )

    # Create a new request to recognize text.
    request = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(
        recognize_text_handler
    )

    # https://developer.apple.com/documentation/vision/vnrequesttextrecognitionlevel
    # default is 0/"accurate"
    if method == "fast":
        request.setRecognitionLevel_(1)
    elif method == "accurate":
        request.setRecognitionLevel_(0)

    # Perform the text-recognition request.
    error = request_handler.performRequests_error_([request], None)

    # Deallocate memory
    request_handler.dealloc()
    request.dealloc()

    output = {
        "image_width": image_width,
        "image_height": image_height,
        "entities": output_entities,
    }
    return output


def extract_text(
    img: Union[str, bytes, "np.ndarray", Literal["clipboard"]],
    origin: Literal["top", "bottom"] = "bottom",
    method: Literal["fast", "accurate"] = "accurate",
) -> dict:
    """
    # From a file
    fname = "/Users/namin/Desktop/Untitled.png"
    print(extract_text(fname))

    # From a numpy array
    from PIL import Image
    array = np.array(Image.open(fname))
    print(extract_text(array))

    # From bytes
    with open(fname, "rb") as fh:
        print(extract_text(fh.read()))

    # From clipboard
    print(extract_text("clipboard"))
    """

    if isinstance(img, str) and img == "clipboard":
        import AppKit

        pasteboard = AppKit.NSPasteboard.generalPasteboard()
        data = pasteboard.dataForType_(AppKit.NSPasteboardTypePNG)
        if data is None:
            raise Exception("Clipboard content is not an image!")
        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            img_path = f.name
            f.write(data)
            output = _extract_text_from_image(img_path, origin, method)
        return output

    elif isinstance(img, str):
        return _extract_text_from_image(img, origin, method)

    elif isinstance(img, bytes):
        with tempfile.NamedTemporaryFile() as f:
            f.write(img)
            img_path = f.name
            output = _extract_text_from_image(img_path, origin, method)
        return output

    elif "ndarray" in str(type(img)):
        from PIL import Image

        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            img_path = f.name
            Image.fromarray(img).save(img_path)
            output = _extract_text_from_image(img_path, origin, method)
        return output

    else:
        raise Exception(f"Unrecognized type for `img`: {type(img)}")


if __name__ == "__main__":
    import rich

    # rich.print(extract_text("assets/example1_input.png"))
    rich.print(extract_text("clipboard"))
