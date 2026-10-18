// ticked: the plots of this row that are not hidden
context.panel.patchFormValue({ plots: mine.filter((p) => !'${hidden:csv}'.split(',').includes(p)) });
