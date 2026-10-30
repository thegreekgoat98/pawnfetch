// Plays the daily puzzle. The server has already turned every solution move into a
// from-square, a to-square and the board after it, so this file only compares the
// visitor's moves with those squares and redraws the board. It knows no chess rules.
(() => {
  const dataEl = document.getElementById("puzzle-data");
  const boardEl = document.querySelector("[data-board]");
  if (!dataEl || !boardEl) return;

  const puzzle = JSON.parse(dataEl.textContent);
  const statusEl = document.querySelector("[data-status]");
  const controls = document.querySelector("[data-controls]");
  const pieceUrl = boardEl.dataset.pieces;
  const pieceNames = { k: "king", q: "queen", r: "rook", b: "bishop", n: "knight", p: "pawn" };
  const side = puzzle.solver === "w" ? "White" : "Black";
  const squares = new Map([...boardEl.querySelectorAll("[data-sq]")].map((el) => [el.dataset.sq, el]));

  let ply = 0; // index of the next move in puzzle.steps
  let placement = puzzle.start;
  let selected = null;
  let dragFrom = null;
  let busy = false; // true while the opponent's reply is being played

  function parse(fenBoard) {
    const pieces = {};
    fenBoard.split("/").forEach((row, index) => {
      let file = 0;
      for (const char of row) {
        if (char >= "1" && char <= "8") {
          file += Number(char);
        } else {
          pieces["abcdefgh"[file] + (8 - index)] = char;
          file += 1;
        }
      }
    });
    return pieces;
  }

  function say(text, state = "") {
    statusEl.textContent = text;
    statusEl.dataset.state = state;
  }

  function setSelected(name) {
    if (selected) squares.get(selected).classList.remove("is-selected");
    selected = name;
    if (selected) squares.get(selected).classList.add("is-selected");
  }

  function draw(fenBoard, lastMove) {
    placement = fenBoard;
    const pieces = parse(fenBoard);
    for (const [name, el] of squares) {
      const char = pieces[name];
      let img = el.querySelector("img");
      if (char) {
        const code = (char === char.toUpperCase() ? "w" : "b") + char.toUpperCase();
        if (!img) {
          img = document.createElement("img");
          img.alt = "";
          img.draggable = false;
          el.prepend(img);
        }
        img.src = `${pieceUrl}${code}.svg`;
        el.setAttribute("aria-label", `${name}, ${code[0] === "w" ? "white" : "black"} ${pieceNames[char.toLowerCase()]}`);
      } else {
        img?.remove();
        el.setAttribute("aria-label", name);
      }
      el.classList.toggle("is-last", Boolean(lastMove) && (name === lastMove.from || name === lastMove.to));
      el.classList.remove("is-selected", "is-hint");
    }
    selected = null;
  }

  function isMine(name) {
    const char = parse(placement)[name];
    return Boolean(char) && (char === char.toUpperCase()) === (puzzle.solver === "w");
  }

  function solved() {
    say("Solved! Nicely done.", "good");
    boardEl.dataset.solved = "";
  }

  function tryMove(from, to) {
    const step = puzzle.steps[ply];
    if (step.from !== from || step.to !== to) {
      setSelected(null);
      const el = squares.get(to);
      el.classList.add("is-wrong");
      setTimeout(() => el.classList.remove("is-wrong"), 500);
      say("Not that one. Try another move.", "bad");
      return;
    }
    draw(step.board, step);
    ply += 1;
    if (ply >= puzzle.steps.length) {
      solved();
      return;
    }
    say("Correct! Here comes the reply…", "good");
    busy = true;
    setTimeout(() => {
      const reply = puzzle.steps[ply];
      draw(reply.board, reply);
      ply += 1;
      busy = false;
      if (ply >= puzzle.steps.length) solved();
      else say(`Your move. ${side} to play.`);
    }, 700);
  }

  function press(name) {
    if (busy || ply >= puzzle.steps.length) return;
    if (isMine(name)) setSelected(name);
    else if (selected) tryMove(selected, name);
  }

  // Mouse and touch: tap-tap, or press on a piece and release on its target square.
  boardEl.addEventListener("pointerdown", (event) => {
    const el = event.target.closest("[data-sq]");
    if (!el) return;
    press(el.dataset.sq);
    dragFrom = selected === el.dataset.sq ? selected : null;
  });
  boardEl.addEventListener("pointerup", (event) => {
    const from = dragFrom;
    dragFrom = null;
    const el = document.elementFromPoint(event.clientX, event.clientY)?.closest("[data-sq]");
    if (from && el && el.dataset.sq !== from && boardEl.contains(el) && !busy && ply < puzzle.steps.length) {
      tryMove(from, el.dataset.sq);
    }
  });
  // Keyboard: squares are buttons, so Enter/Space fires a click with no pointer (detail 0).
  boardEl.addEventListener("click", (event) => {
    const el = event.target.closest("[data-sq]");
    if (el && event.detail === 0) press(el.dataset.sq);
  });

  controls.hidden = false;
  controls.querySelector("[data-hint]").addEventListener("click", () => {
    if (busy || ply >= puzzle.steps.length) return;
    const from = squares.get(puzzle.steps[ply].from);
    from.classList.add("is-hint");
    say("Hint: move the highlighted piece.");
  });
  controls.querySelector("[data-reset]").addEventListener("click", () => {
    if (busy) return;
    ply = 0;
    delete boardEl.dataset.solved;
    draw(puzzle.start, null);
    say(`Find the best move for ${side}.`);
  });
})();
