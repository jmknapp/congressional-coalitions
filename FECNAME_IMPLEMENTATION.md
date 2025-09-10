# FEC Name Field Implementation

## Overview

This implementation adds a `fecname` field to the `challengers2026` table to solve name formatting issues when updating challenger data from FEC CSV files. The `fecname` field stores the exact FEC name format and serves as the primary key for matching, while the `challenger_name` field can be used for display purposes with nicknames, proper formatting, etc.

## Benefits

1. **Reliable Matching**: Uses exact FEC name format as the primary matching key
2. **Flexible Display Names**: Allows using nicknames, proper formatting, or any display name in `challenger_name`
3. **Backward Compatibility**: Maintains fallback matching for existing data
4. **Future-Proof**: Handles new CSV data without name format conflicts

## Implementation Details

### Database Changes

- **New Field**: `fecname VARCHAR(200) NULL` added to `challengers2026` table
- **Index**: Added index on `fecname` for faster lookups
- **Migration**: Script provided to add field and populate existing records

### Model Updates

- **Challenger2026 Model**: Updated to include `fecname` field
- **API Endpoints**: Updated to handle `fecname` in create/update operations
- **FEC Population**: Uses `fecname` as primary matching key with fallbacks

### Frontend Changes

- **Add/Edit Forms**: Added FEC Name field (optional)
- **Developer Mode**: Shows FEC name in challenger cards for debugging
- **User Experience**: Clear labeling and help text for the FEC name field

## Usage

### For New Challengers

1. **Display Name**: Enter the name as you want it displayed (can use nicknames, proper formatting)
2. **FEC Name**: Enter the exact FEC format (e.g., "SMITH, JOHN MR.") for reliable matching
3. **Auto-Population**: When using "Populate from FEC", the FEC name is automatically set

### For Existing Challengers

1. **Migration**: Run the migration script to add the field
2. **Population**: Existing records get a converted FEC name as a starting point
3. **Updates**: Use "Populate from FEC" to set proper FEC names for all records

## Migration Steps

1. **Run Migration Script**:
   ```bash
   python scripts/add_fecname_to_challengers.py
   ```

2. **Update Existing Data**:
   - Use "Populate from FEC" button to set proper FEC names
   - Or manually edit challengers to add FEC names

3. **Verify Implementation**:
   - Check that new CSV uploads work correctly
   - Verify that name matching is more reliable

## Technical Details

### Matching Logic

The system now uses this priority order for matching:
1. **Primary**: Exact `fecname` match
2. **Fallback 1**: Original FEC name in `challenger_name`
3. **Fallback 2**: Formatted name in `challenger_name`

### FEC Name Format

FEC names are typically in format: `"LAST, FIRST TITLE"`
- Example: `"SMITH, JOHN MR."`
- Example: `"JONES, MARY MS."`
- Example: `"BROWN, ROBERT"` (no title)

### Display Name Flexibility

The `challenger_name` field can now contain:
- Nicknames: "Johnny Smith"
- Proper formatting: "Mr. John Smith"
- Any preferred display name

## Files Modified

1. **Database**:
   - `scripts/add_fecname_to_challengers.py` (new migration script)
   - `scripts/setup_challengers_table.py` (updated model)

2. **Backend**:
   - `app.py` (updated API endpoints and FEC population logic)

3. **Frontend**:
   - `templates/challengers.html` (updated forms and display)

## Testing

To test the implementation:

1. **Add a new challenger** with both display name and FEC name
2. **Run "Populate from FEC"** to verify matching works
3. **Upload new CSV data** to ensure no duplicate entries
4. **Edit existing challengers** to add FEC names
5. **Verify developer mode** shows FEC names correctly

## Future Enhancements

1. **Auto-Detection**: Could add logic to automatically detect FEC names from display names
2. **Validation**: Could add validation to ensure FEC names match expected format
3. **Bulk Operations**: Could add bulk FEC name setting functionality
4. **Import/Export**: Could include FEC names in data export/import operations

## Troubleshooting

### Common Issues

1. **Missing FEC Names**: Use "Populate from FEC" to set them automatically
2. **Duplicate Entries**: Check that FEC names are set correctly for existing challengers
3. **Matching Failures**: Verify FEC name format matches exactly (case-sensitive)

### Debugging

- Enable developer mode to see FEC names in challenger cards
- Check database directly to verify FEC names are stored correctly
- Use browser developer tools to inspect API requests/responses
