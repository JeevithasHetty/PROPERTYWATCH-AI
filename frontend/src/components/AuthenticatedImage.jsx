import React, { useEffect, useState } from 'react';
import apiClient from '../api/client';

const PRIVATE_SNAPSHOT_PATH = /^\/api\/properties\/(\d+)\/snapshots\/(\d+)\/image$/;

const AuthenticatedImage = ({ src, alt, style, ...imageProps }) => {
  const [loadedImage, setLoadedImage] = useState({ src: null, url: null, error: false });
  const privatePath = src?.match(PRIVATE_SNAPSHOT_PATH);
  const imageUrl = privatePath && loadedImage.src === src ? loadedImage.url : null;
  const loadError = privatePath && loadedImage.src === src && loadedImage.error;

  useEffect(() => {
    const path = src?.match(PRIVATE_SNAPSHOT_PATH);
    if (!path) return undefined;

    let disposed = false;
    let objectUrl;
    apiClient.getPropertySnapshotImage(path[1], path[2])
      .then((response) => {
        objectUrl = URL.createObjectURL(response.data);
        if (disposed) {
          URL.revokeObjectURL(objectUrl);
        } else {
          setLoadedImage({ src, url: objectUrl, error: false });
        }
      })
      .catch(() => {
        if (!disposed) setLoadedImage({ src, url: null, error: true });
      });

    return () => {
      disposed = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [src]);

  if (privatePath && loadError) {
    return (
      <div
        role="img"
        aria-label={`${alt || 'Private image'} unavailable`}
        style={{ ...style, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      >
        Private image unavailable
      </div>
    );
  }

  return <img src={privatePath ? imageUrl || undefined : src} alt={alt} style={style} {...imageProps} />;
};

export default AuthenticatedImage;
