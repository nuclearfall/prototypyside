# ProtoTypySide

## What it can currently do:
- Build and save component templates.
- Build and save custom single page grid layout templates
- Pagination models are built but not implemented

What it will eventually do:
- Data merge of text and images (from path)
- Layout preview
- Non-grid based layout templates
- Automated layout of pagination models
	- custom (grid static/merged templates)
    - clustered
    - token (static template)
    - over sized (this generates pages with overlap for templates larger than a single page for custom board making, etc)
- Exporting to various formats (pdf/png)
- Printing directly to printers supported by Qt6.

This software doesn't aim to replace inDesign or anything like that. It's not built for making complex layered images. It's purpose driven: I want to prototype physical board game components and sometimes make custom components for games I already have. This makes life easier since I have a difficult time finding any layout software which is built specifically with my needs in mind. I can create a single card template, import the data and have all cards print straight to the printer without having to export anything. Qt6 hassome kind of print magic that allows it to do this.

## Components
Component templates are composed from two basic elements: text and images. You will be able to make components using components (for things like reusing a scoring track component and placing it atop a board template, but for now, it's just the two.

Component instances are the things that go in the layout slots of a layout template. If you aren't merging data, this is just a copy of your component template

## Layouts:
Layout templates are composed of one element: layout slots. What goes in those slots is up to you. You can add what types of components you want to your component panel. It's a basic grid, so you just drag the components into slots. You can just have the entire grid autopopulate from a single component template then data merge card info or whatever you have from a csv format file. If data has merged, the template will create layout instances of the page size until all component instances have been populated.

## Data Merge
Like inDesign, you format the column headers of your spreadsheet so that they begin with an "@" and do the same for the elements in your template. Choose import from... in the File menu and the data will auto-populate in the layout.

## Pagination:
Not only should the software create templates, but it should correctly fill them based on simple input parameters. If you have a single card template, place it into a single slot on the page layout, set pagination to Single Template and it should correctly populate pages until each card from merge data has been printed. If you have a board component template (one that exceeds the size of a single page). It should print that board in sections with overlap to allow for an actual folding board.
