// the fields whose value differs from the one the panel started with, or applied last
const changed = ({ elements, initial }) => elements.filter((e) => e.value !== initial[e.id]);
