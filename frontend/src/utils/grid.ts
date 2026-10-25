export interface Cell {
  row: number;
  col: number;
  type: string;
  number: number | null;
  startsAcross: boolean;
  startsDown: boolean;
}

export function build2DGrid(cells: Cell[], width: number, height: number): Cell[][] {
  const grid: Cell[][] = [];
  for (let row = 0; row < height; row++) {
    grid[row] = [];
    for (let col = 0; col < width; col++) {
      grid[row][col] = {
        row,
        col,
        type: "black",
        number: null,
        startsAcross: false,
        startsDown: false,
      };
    }
  }
  for (const cell of cells) {
    if (cell.row >= 0 && cell.row < height && cell.col >= 0 && cell.col < width) {
      grid[cell.row][cell.col] = cell;
    }
  }
  return grid;
}
