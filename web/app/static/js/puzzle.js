// Plays one Lichess puzzle on cm-chessboard, with chess.js for the rules.
//
// The server sends the FEN and the solution as UCI moves ("e2e4", "e7e8q"). The FEN is the
// position *before* the opponent's move: moves[0] is played automatically, then the visitor
// plays moves[1], the opponent replies with moves[2], and so on.
import {Chessboard, BORDER_TYPE, COLOR, INPUT_EVENT_TYPE} from "../vendor/cm-chessboard/src/Chessboard.js"
import {Markers, MARKER_TYPE} from "../vendor/cm-chessboard/src/extensions/markers/Markers.js"
import {PROMOTION_DIALOG_RESULT_TYPE, PromotionDialog} from "../vendor/cm-chessboard/src/extensions/promotion-dialog/PromotionDialog.js"
import {Accessibility} from "../vendor/cm-chessboard/src/extensions/accessibility/Accessibility.js"
import {RightClickAnnotator} from "../vendor/cm-chessboard/src/extensions/right-click-annotator/RightClickAnnotator.js"
import {Chess} from "../vendor/chess.js/chess.js"

// Marker types must be the same object every time (cm-chessboard compares by reference).
const LAST_MOVE = {class: "marker-last", slice: "markerSquare"}
const WRONG = {class: "marker-wrong", slice: "markerSquare"}
const HINT = {class: "marker-hint", slice: "markerFrame"}
const REPLY_DELAY = 600

const data = JSON.parse(document.getElementById("puzzle-data").textContent)
const boardEl = document.querySelector("[data-board]")
const statusEl = document.querySelector("[data-status]")
const controlsEl = document.querySelector("[data-controls]")
const nextEl = document.querySelector("[data-next]")
const color = data.solver === "w" ? COLOR.white : COLOR.black
const side = data.solver === "w" ? "White" : "Black"
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const uci = (move) => move.from + move.to + (move.promotion || "")
const toMove = (text) => ({from: text.slice(0, 2), to: text.slice(2, 4), promotion: text[4]})

let game = new Chess(data.fen)
let ply = 0 // index of the next move in data.moves
let busy = true // true while moves are being played automatically
let done = false

function say(text, state = "") {
    statusEl.textContent = text
    statusEl.dataset.state = state
}

const board = new Chessboard(boardEl, {
    position: data.fen,
    orientation: color,
    assetsUrl: "/static/vendor/cm-chessboard/assets/",
    style: {
        cssClass: "pawnfetch",
        borderType: BORDER_TYPE.none,
        pieces: {file: "/static/pieces/cburnett.svg"},
        animationDuration: 220,
    },
    extensions: [
        {class: Markers, props: {autoMarkers: MARKER_TYPE.square}},
        {class: PromotionDialog},
        {class: Accessibility, props: {language: "en", keyboardMoveInput: true}},
        // Right-click arrows and circles, like chess.com. Adds the Arrows extension itself.
        {class: RightClickAnnotator},
    ],
})

// Arrows and circles are the visitor's scribbles: clear them on a left click, like chess.com,
// and whenever the position changes.
const clearAnnotations = () => board.setAnnotations({})
boardEl.addEventListener("mousedown", (event) => {
    if (event.button === 0) clearAnnotations()
})

function markLastMove(move) {
    board.removeMarkers(LAST_MOVE)
    board.addMarker(LAST_MOVE, move.from)
    board.addMarker(LAST_MOVE, move.to)
}

// Plays data.moves[ply] on the board and advances.
async function playNext() {
    const move = game.move(toMove(data.moves[ply]))
    ply += 1
    clearAnnotations()
    await board.setPosition(game.fen(), true)
    markLastMove(move)
    return move
}

function finish(text, state) {
    done = true
    board.disableMoveInput()
    nextEl.dataset.ready = ""
    say(text, state)
}

// Lichess: every move must be the solution move, except that any mate on the last move counts.
function isCorrect(move) {
    if (uci(move) === data.moves[ply]) return true
    if (ply !== data.moves.length - 1) return false
    const check = new Chess(game.fen())
    check.move(move)
    return check.isCheckmate()
}

async function tryMove(from, to, promotion) {
    let move
    try {
        move = new Chess(game.fen()).move({from, to, promotion})
    } catch {
        await board.setPosition(game.fen(), true)
        return
    }
    if (!isCorrect(move)) {
        say("Not that one. Try another move.", "bad")
        board.addMarker(WRONG, to)
        await wait(450)
        board.removeMarkers(WRONG)
        await board.setPosition(game.fen(), true)
        return
    }
    game.move(move)
    ply += 1
    board.removeMarkers(HINT)
    await board.setPosition(game.fen(), true) // also fixes castling, en passant and promotion
    markLastMove(move)
    if (ply >= data.moves.length) {
        boardEl.dataset.solved = ""
        finish("Solved! Nicely done.", "good")
        return
    }
    say("Correct! Keep going…", "good")
    busy = true
    await wait(REPLY_DELAY)
    await playNext()
    busy = false
    say(`Your move. ${side} to play.`)
}

function onInput(event) {
    switch (event.type) {
        case INPUT_EVENT_TYPE.moveInputStarted: {
            if (busy || done) return false
            const moves = game.moves({square: event.squareFrom, verbose: true})
            board.addLegalMovesMarkers(moves)
            return moves.length > 0
        }
        case INPUT_EVENT_TYPE.validateMoveInput: {
            board.removeLegalMovesMarkers()
            const legal = game.moves({square: event.squareFrom, verbose: true}).filter((m) => m.to === event.squareTo)
            if (!legal.length) return false
            const {squareFrom: from, squareTo: to} = event
            if (legal.some((m) => m.promotion)) {
                board.showPromotionDialog(to, color, (result) => {
                    if (result.type === PROMOTION_DIALOG_RESULT_TYPE.pieceSelected) {
                        tryMove(from, to, result.piece.charAt(1))
                    } else {
                        board.setPosition(game.fen(), true)
                    }
                })
                return true
            }
            // Let cm-chessboard finish moving the piece before we check the move and redraw.
            setTimeout(() => tryMove(from, to), 0)
            return true
        }
        case INPUT_EVENT_TYPE.moveInputCanceled:
            board.removeLegalMovesMarkers()
            break
    }
}

// Set the puzzle up: show the starting position, then the opponent's first move.
async function start() {
    busy = true
    done = false
    game = new Chess(data.fen)
    ply = 0
    delete boardEl.dataset.solved
    delete nextEl.dataset.ready
    clearAnnotations()
    board.removeMarkers()
    board.disableMoveInput()
    await board.setPosition(data.fen, false)
    say("Watch the opponent's move…")
    await wait(REPLY_DELAY)
    await playNext()
    board.enableMoveInput(onInput, color)
    busy = false
    say(`Your move. Find the best move for ${side}.`)
}

function readable() {
    // Check every solution move against the position up front, so a broken puzzle fails clearly.
    try {
        const check = new Chess(data.fen)
        return data.moves.length >= 2 && data.moves.every((m) => check.move(toMove(m)))
    } catch {
        return false
    }
}

if (!readable()) {
    say("This puzzle can't be played here. Try the next one.")
    nextEl.dataset.ready = ""
} else {
    controlsEl.hidden = false
    document.querySelector("[data-help]").hidden = false
    controlsEl.querySelector("[data-hint]").addEventListener("click", () => {
        if (busy || done) return
        board.removeMarkers(HINT)
        board.addMarker(HINT, toMove(data.moves[ply]).from)
        say("Hint: move the highlighted piece.")
    })
    controlsEl.querySelector("[data-solution]").addEventListener("click", async () => {
        if (busy || done) return
        busy = true
        board.disableMoveInput()
        board.removeMarkers(HINT)
        say("Here's the solution…")
        while (ply < data.moves.length) {
            await playNext()
            await wait(REPLY_DELAY)
        }
        busy = false
        finish("That's the solution. Try the next one!")
    })
    controlsEl.querySelector("[data-reset]").addEventListener("click", () => {
        if (!busy) start()
    })
    start()
}