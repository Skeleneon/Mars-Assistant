num_dict_ones = {"zero":0,"one":1,"two":1,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,
            "eleven":11,"twelve":12,"thirteen":13,"fourteen":14,"fifteen":15,"sixteen":16,"seventeen":17,
            "eighteen":18,"nineteen":19}

num_dict_tens = {"twenty":20,"thirty":30,"forty":40,"fifty":50,"sixty":60,"seventy":70,"eighty":80,"ninety":90,}



def convertToNum(sentence):
    
    tens = 0
    ones = 0
    sentence2 = sentence.split()

    finished_sentence=""
    next=True
    
    for i in range(0,len(sentence2)):
        if next==False:
            next=True
            continue
        
        if sentence2[i] in num_dict_tens or sentence2[i] in num_dict_ones:
            if sentence2[i] in num_dict_tens:
                tens = num_dict_tens[sentence2[i]]
                if len(sentence2)>1 and sentence2[i+1] in num_dict_ones:
                    ones = num_dict_ones[sentence2[i+1]]
                    final_num = tens+ones
                    finished_sentence+=str(final_num)+" "
                    next=False
                    
                else:
                    final_num = tens
                    finished_sentence+=str(final_num)+" "
            else:
                ones = num_dict_ones[sentence2[i]]
                final_num = ones
                finished_sentence+=str(final_num)+" "
        else:
            finished_sentence+=sentence2[i]+" "

    return finished_sentence


print(convertToNum("set volume to twenty five"))

        
            

    