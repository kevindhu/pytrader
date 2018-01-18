//analyze candles, see if there is a base



function Candle(start, end, high, low) {
	this.start = start;
	this.end = end;
	this.high = high;
	this.low = low;
}

function Coin(base, chart) {
	this.chart = chart;
	this.base = base;
}




/*** Checks if the candle end at the index of the chart qualifies as base ***/
//chart = array of Candles
//index = number on the chart
//hours = how many hours away to look for high

function isBase(index, chart, hours) {
	var curr = chart[index];
	var prev = chart[index-1];


	//find if curr low is lower than previous candle's low
	var isBottom = curr.low < prev.low;


	//find if next few hours' high is 10-30% higher than the candle's lwo 
	var maxHigh = -1;
	for (var i = 0; i<hours; i++) {
		var currHigh = chart[index + i + 1];
		if (maxHigh < currHigh) {
			maxHigh = currHigh;
		}
	}
	var hasJump = (maxHigh / curr.low > 1.3);


	return hasJump && isBottom;
}




/*** find bases up to a certain index ***/
//returns a list of [candle lows,indexes]
function findBases(chart, index) {
	var ret = [];
	for (var i = 0; i<index; i++) {
		//check if base

		if (isBase(index, chart, 3)) {
			var candle = chart[index];
			ret.push([candle.low, index]);
		}
	} 
	return ret;
}



//a tick for a certain coin
function tick(coin, currPrice) {
	if currPrice
}

function tradeBase() {
	


}
