#!/bin/bash

# Batch process all House bills in Congress 119
# This script processes bills in batches of 50

CONGRESS=119
BATCH_SIZE=50
TOTAL_BILLS=5874  # Total House bills in Congress 119

echo "Starting batch processing of $TOTAL_BILLS House bills in Congress $CONGRESS"
echo "Batch size: $BATCH_SIZE"
echo "=================================="

for ((offset=0; offset<TOTAL_BILLS; offset+=BATCH_SIZE)); do
    echo ""
    echo "Processing batch starting at offset $offset..."
    echo "=================================="
    
    # Calculate actual limit for this batch
    remaining=$((TOTAL_BILLS - offset))
    if [ $remaining -lt $BATCH_SIZE ]; then
        limit=$remaining
    else
        limit=$BATCH_SIZE
    fi
    
    echo "Processing bills $offset to $((offset + limit - 1)) of $TOTAL_BILLS"
    
    # Run the script
    venv/bin/python scripts/load_house_sponsors_cosponsors.py \
        --congress $CONGRESS \
        --limit $limit \
        --offset $offset
    
    echo "Completed batch at offset $offset"
    echo "=================================="
    
    # Optional: add a delay between batches
    sleep 5
done

echo ""
echo "All batches completed!"
echo "Total bills processed: $TOTAL_BILLS"
