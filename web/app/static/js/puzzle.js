// Plays the daily puzzle on cm-chessboard, with chess.js for the rules.
//
// The server sends the starting FEN, whose turn it is, and the solution as SAN moves
// ("Nxg6+", "hxg6", "Qh4#"). chess.js turns those into real moves and tells us which moves
// are legal; cm-chessboard draws the board, drags the pieces and animates them.
import {Chessboard, BORDER_TYPE, COLOR, INPUT_EVENT_TYPE} from "../vendor/cm-chessboard/src/Chessboard.js"
import {Markers, MARKER_TYPE} from "../vendor/cm-chessboard/src/extensions/markers/Markers.js"
import {PROMOTION_DIALOG_RESULT_TYPE, PromotionDialog} from "../vendor/cm-chessboard/src/extensions/promotion-dialog/PromotionDialog.js"
import {Accessibility} from "../vendor/cm-chessboard/src/extensions/accessibility/Accessibility.js"
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
const side = data.solver === "w" ? "White" : "Black"

function say(text, state = "") {
    statusEl.textContent = text
    statusEl.dataset.state = state
}

// Turn the SAN solution into verbose moves ({from, to, promotion, ...}) once, up front.
// If chess.js can't follow it, the puzzle isn't playable here and we say so.
function readSolution() {
    try {
        const game = new Chess(data.fen)
        return data.moves.map((san) => game.move(san))
    } catch {
        return null
    }
}

const solution = data.moves.length ? readSolution() : null

if (!solution) {
    say("This puzzle can't be played here. Try it on chess.com.")
} else {
    let game = new Chess(data.fen)
    let ply = 0 // index of the next move in `solution`
    let busy = false // true while the opponent's reply is being played

    const board = new Chessboard(boardEl, {
        position: data.fen,
        orientation: data.solver === "w" ? COLOR.white : COLOR.black,
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
        ],
    })

    const markLastMove = (move) => {
        board.removeMarkers(LAST_MOVE)
        board.addMarker(LAST_MOVE, move.from)
        board.addMarker(LAST_MOVE, move.to)
    }

    const finished = () => ply >= solution.length

    function solved() {
        board.disableMoveInput()
        boardEl.dataset.solved = ""
        say("Solved! Nicely done.", "good")
    }

    function playReply() {
        busy = true
        setTimeout(async () => {
            const reply = game.move(solution[ply].san)
            ply += 1
            await board.setPosition(game.fen(), true)
            markLastMove(reply)
            busy = false
            if (finished()) solved()
            else say(`Your move. ${side} to play.`)
        }, REPLY_DELAY)
    }

    // A move counts if it is the solution move, or if it is the last move and also mates
    // (some mate-in-ones have more than one mating move).
    function isCorrect(move) {
        const expected = solution[ply]
        if (move.from === expected.from && move.to === expected.to && (move.promotion || "") === (expected.promotion || "")) {
            return true
        }
        if (ply === solution.length - 1) {
            const check = new Chess(game.fen())
            check.move(move)
            return check.isCheckmate()
        }
        return false
    }

    async function tryMove(from, to, promotion) {
        const candidate = new Chess(game.fen())
        let move
        try {
            move = candidate.move({from, to, promotion})
        } catch {
            await board.setPosition(game.fen(), true)
            return
        }
        if (!isCorrect(move)) {
            say("Not that one. Try another move.", "bad")
            board.addMarker(WRONG, to)
            setTimeout(async () => {
                board.removeMarkers(WRONG)
                await board.setPosition(game.fen(), true)
            }, 450)
            return
        }
        game.move(move)
        ply += 1
        board.removeMarkers(HINT)
        // setPosition (not just the drag) so castling, en passant and promotion look right.
        await board.setPosition(game.fen(), true)
        markLastMove(move)
        if (finished()) {
            solved()
            return
        }
        say("Correct! Here comes the reply…", "good")
        playReply()
    }

    function onInput(event) {
        switch (event.type) {
            case INPUT_EVENT_TYPE.moveInputStarted: {
                if (busy || finished()) return false
                const moves = game.moves({square: event.squareFrom, verbose: true})
                board.addLegalMovesMarkers(moves)
                return moves.length > 0
            }
            case INPUT_EVENT_TYPE.validateMoveInput: {
                board.removeLegalMovesMarkers()
                const legal = game.moves({square: event.squareFrom, verbose: true}).filter((m) => m.to === event.squareTo)
                if (!legal.length) return false
                if (legal.some((m) => m.promotion)) {
                    const color = data.solver === "w" ? COLOR.white : COLOR.black
                    board.showPromotionDialog(event.squareTo, color, (result) => {
                        if (result.type === PROMOTION_DIALOG_RESULT_TYPE.pieceSelected) {
                            tryMove(event.squareFrom, event.squareTo, result.piece.charAt(1))
                        } else {
                            board.setPosition(game.fen(), true)
                        }
                    })
                    return true
                }
                tryMove(event.squareFrom, event.squareTo)
                return true
            }
            case INPUT_EVENT_TYPE.moveInputCanceled:
                board.removeLegalMovesMarkers()
                break
        }
    }

    board.enableMoveInput(onInput, data.solver === "w" ? COLOR.white : COLOR.black)

    controlsEl.hidden = false
    document.querySelector("[data-help]").hidden = false
    controlsEl.querySelector("[data-hint]").addEventListener("click", () => {
        if (busy || finished()) return
        board.removeMarkers(HINT)
        board.addMarker(HINT, solution[ply].from)
        say("Hint: move the highlighted piece.")
    })
    controlsEl.querySelector("[data-reset]").addEventListener("click", async () => {
        if (busy) return
        game = new Chess(data.fen)
        ply = 0
        delete boardEl.dataset.solved
        board.removeMarkers()
        await board.setPosition(data.fen, true)
        board.disableMoveInput() // enabling twice throws, and input is still on unless solved
        board.enableMoveInput(onInput, data.solver === "w" ? COLOR.white : COLOR.black)
        say(`Find the best move for ${side}.`)
    })
}
