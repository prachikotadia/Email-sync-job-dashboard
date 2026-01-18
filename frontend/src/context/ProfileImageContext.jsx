import { createContext, useContext, useState, useEffect } from 'react'
import { useAuth } from './AuthContext'

const ProfileImageContext = createContext(null)

const PROFILE_IMAGE_STORAGE_KEY = 'jobpulse_profile_image'

export function ProfileImageProvider({ children }) {
  const { user } = useAuth()
  const [profileImage, setProfileImage] = useState(null)

  // Load profile image from localStorage on mount or when user changes
  useEffect(() => {
    if (user?.email) {
      const stored = localStorage.getItem(`${PROFILE_IMAGE_STORAGE_KEY}_${user.email}`)
      if (stored) {
        setProfileImage(stored)
      } else {
        setProfileImage(null)
      }
    } else {
      setProfileImage(null)
    }
  }, [user?.email])

  // Compress and crop image to perfect square for profile picture
  const compressImage = (file, size = 400, quality = 0.9) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = (e) => {
        const img = new Image()
        img.onload = () => {
          // Ensure image is loaded
          if (img.width === 0 || img.height === 0) {
            reject(new Error('Invalid image dimensions'))
            return
          }

          const canvas = document.createElement('canvas')
          canvas.width = size
          canvas.height = size

          const ctx = canvas.getContext('2d')
          
          // Set high quality rendering
          ctx.imageSmoothingEnabled = true
          ctx.imageSmoothingQuality = 'high'
          
          // Calculate source dimensions for center crop to perfect square
          const sourceSize = Math.min(img.width, img.height)
          const sourceX = Math.max(0, (img.width - sourceSize) / 2)
          const sourceY = Math.max(0, (img.height - sourceSize) / 2)

          // Clear canvas with white background (for transparency handling)
          ctx.fillStyle = '#ffffff'
          ctx.fillRect(0, 0, size, size)

          // Draw image centered and cropped to square
          ctx.drawImage(
            img,
            sourceX, sourceY, sourceSize, sourceSize, // Source: center crop
            0, 0, size, size // Destination: full canvas (perfect square)
          )

          // Convert to blob with compression
          canvas.toBlob(
            (blob) => {
              if (blob) {
                const reader = new FileReader()
                reader.onload = () => {
                  const dataUrl = reader.result
                  // Verify it's a valid data URL
                  if (dataUrl && dataUrl.startsWith('data:image')) {
                    resolve(dataUrl)
                  } else {
                    reject(new Error('Failed to generate image data'))
                  }
                }
                reader.onerror = () => reject(new Error('Failed to compress image'))
                reader.readAsDataURL(blob)
              } else {
                reject(new Error('Failed to compress image'))
              }
            },
            'image/jpeg',
            quality
          )
        }
        img.onerror = () => reject(new Error('Failed to load image'))
        img.src = e.target.result
      }
      reader.onerror = () => reject(new Error('Failed to read image file'))
      reader.readAsDataURL(file)
    })
  }

  const uploadProfileImage = (file) => {
    return new Promise((resolve, reject) => {
      if (!file || !file.type.startsWith('image/')) {
        reject(new Error('Please select a valid image file'))
        return
      }

      if (file.size > 5 * 1024 * 1024) { // 5MB limit
        reject(new Error('Image size must be less than 5MB'))
        return
      }

      // Compress image before storing
      compressImage(file)
        .then((compressedImageUrl) => {
          if (user?.email) {
            try {
              // Check if compressed image is still too large (localStorage limit ~5-10MB)
              const sizeInBytes = new Blob([compressedImageUrl]).size
              if (sizeInBytes > 2 * 1024 * 1024) { // 2MB limit for localStorage
                reject(new Error('Image is too large even after compression. Please use a smaller image.'))
                return
              }

              localStorage.setItem(`${PROFILE_IMAGE_STORAGE_KEY}_${user.email}`, compressedImageUrl)
              setProfileImage(compressedImageUrl)
              resolve(compressedImageUrl)
            } catch (error) {
              if (error.name === 'QuotaExceededError' || error.message.includes('quota')) {
                reject(new Error('Storage limit exceeded. Please use a smaller image or clear some data.'))
              } else {
                reject(new Error('Failed to save image. Please try again.'))
              }
            }
          } else {
            reject(new Error('User not authenticated'))
          }
        })
        .catch((error) => {
          reject(error)
        })
    })
  }

  const removeProfileImage = () => {
    if (user?.email) {
      localStorage.removeItem(`${PROFILE_IMAGE_STORAGE_KEY}_${user.email}`)
      setProfileImage(null)
    }
  }

  const value = {
    profileImage,
    uploadProfileImage,
    removeProfileImage,
  }

  return <ProfileImageContext.Provider value={value}>{children}</ProfileImageContext.Provider>
}

export function useProfileImage() {
  const context = useContext(ProfileImageContext)
  if (!context) {
    throw new Error('useProfileImage must be used within ProfileImageProvider')
  }
  return context
}
