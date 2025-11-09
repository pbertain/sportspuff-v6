-- Migration script to add new columns to stadiums table
-- Adds: full_alt_name, alt_name, image_name

-- Add new columns if they don't exist
DO $$
BEGIN
    -- Add full_alt_name column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='stadiums' AND column_name='full_alt_name'
    ) THEN
        ALTER TABLE stadiums ADD COLUMN full_alt_name VARCHAR(255);
    END IF;

    -- Add alt_name column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='stadiums' AND column_name='alt_name'
    ) THEN
        ALTER TABLE stadiums ADD COLUMN alt_name VARCHAR(255);
    END IF;

    -- Add image_name column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='stadiums' AND column_name='image_name'
    ) THEN
        ALTER TABLE stadiums ADD COLUMN image_name VARCHAR(500);
    END IF;
END $$;

-- Verify columns were added
SELECT column_name, data_type, character_maximum_length 
FROM information_schema.columns 
WHERE table_name = 'stadiums' 
AND column_name IN ('full_alt_name', 'alt_name', 'image_name')
ORDER BY column_name;

