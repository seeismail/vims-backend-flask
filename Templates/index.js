import React from "react";

const Cam = () => {
    return (
        <div>
            <img
                src="http://localhost:5000/video_feed" // /video_feed/<input_path>/<output_path>
                alt="Video"
            />
        </div>
    );
};

export default Cam;
